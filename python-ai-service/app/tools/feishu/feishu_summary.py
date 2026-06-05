"""
飞书摘要 — 聊天消息的提示词构建器和 LLM 摘要生成器。

将评分后的消息转换为结构化摘要提示词，
调用 LLM 提取关键信息，并返回格式化结果。

输出格式:
  [通知] ...
  [任务] ...
  [会议] ...
  [风险] ...
  [其他] ...
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.tools.feishu.feishu_message_filter import ScoredMessage

logger = logging.getLogger(__name__)


# ============================================================
# 摘要系统提示词
# ============================================================

SUMMARY_SYSTEM_PROMPT = """你是一位资深企业助理 AI。你的任务是阅读企业聊天消息并生成结构化摘要。

## 摘要规则

1. 提取并分类信息到各个部分:
   - [通知]: 官方公告、发布通知、政策变更
   - [任务]: 分配的任务、行动项、待办事项、截止日期
   - [会议]: 会议通知、评审安排、会议结论
   - [风险]: 事故、Bug、告警、紧急问题、生产问题
   - [其他]: 不符合上述类别的重要讨论

2. 对于每个条目，包含:
   - 谁 (发送者姓名，如有)
   - 什么 (核心内容，1-2 行)
   - 何时 (时间或截止日期)

3. 质量要求:
   - 不要简单地逐字重复聊天消息
   - 优先提取决策、结论和行动项，而非闲聊
   - 如果一个主题跨越多条消息，将其合并为一个条目
   - 略去琐碎对话 (问候、表情符号、无关话题)
   - 使用专业但友好的语气

4. 输出格式:
   每个部分以标记开头，后跟要点 (- )。
   如果某个部分没有相关内容，输出 "无"。
   保持总摘要简洁，不超过 500 字。"""


SUMMARY_USER_TEMPLATE = """以下是企业聊天群中的近期重要消息。

聊天名称: {chat_name}
时间范围: 最近 {hours} 小时
消息总数: {total_count}
重要消息 (已过滤): {important_count}

---
{message_list}
---

请按照格式规则生成结构化摘要。"""


# ============================================================
# 消息格式化器 (用于提示词)
# ============================================================

def format_messages_for_prompt(
    messages: List[ScoredMessage],
    max_chars_per_msg: int = 300,
) -> str:
    """将评分后的消息格式化为紧凑的提示词字符串。

    每条消息格式化为:
      [时间] 发送者 (分数:N, 类别:类别):
        文本...

    消息按类别分组以便 LLM 处理。

    参数:
        messages: 按重要性排序的评分消息。
        max_chars_per_msg: 每条消息文本的最大字符数 (截断)。

    返回:
        格式化的字符串，可直接插入提示词。
    """
    if not messages:
        return "(未找到重要消息)"

    lines: List[str] = []
    current_category = ""

    for sm in messages:
        # 切换类别时添加类别标题
        cat_label = _category_label(sm.category)
        if sm.category != current_category:
            current_category = sm.category
            lines.append(f"\n--- {cat_label} ---")

        # 截断长消息
        text = sm.plain_text
        if len(text) > max_chars_per_msg:
            text = text[:max_chars_per_msg - 3] + "..."

        # 格式: [HH:MM] 姓名: 文本
        time_str = sm.time_str or "--:--"
        at_flag = " [@所有人]" if sm.is_at_everyone else ""
        lines.append(f"[{time_str}] {sm.sender_name}{at_flag}: {text}")

    return "\n".join(lines)


def _category_label(category: str) -> str:
    """用于提示显示的中文类别标签。"""
    labels = {
        "notification": "Notification/Announcement",
        "meeting": "Meeting",
        "task": "Task/To-do",
        "risk": "Risk/Incident",
        "other": "Other Important",
    }
    return labels.get(category, category)


# ============================================================
# 摘要生成器
# ============================================================

class FeishuSummaryGenerator:
    """使用 LLM 从评分消息生成结构化摘要。

    用法:
        gen = FeishuSummaryGenerator(llm_chat_fn)
        summary = await gen.generate(messages, chat_name="技术团队")
    """

    def __init__(self, llm_chat_fn):
        """使用异步 LLM 聊天函数初始化。

        参数:
            llm_chat_fn: 异步函数，签名:
                async def fn(messages, temperature, max_tokens) -> LLMResponse
                其中 LLMResponse 有 .content (str)。
        """
        self._chat = llm_chat_fn

    async def generate(
        self,
        messages: List[ScoredMessage],
        chat_name: str = "",
        hours_back: int = 24,
        total_count: int = 0,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> Dict[str, Any]:
        """从评分消息生成结构化摘要。

        流程:
          1. 将消息格式化为提示词字符串 (按类别分组)
          2. 构建系统 + 用户消息
          3. 调用 LLM
          4. 解析输出为结构化部分 (解析失败时回退)

        参数:
            messages: 按重要性排序的评分消息。
            chat_name: 聊天群名称，用于上下文。
            hours_back: 显示的时间窗口。
            total_count: 原始消息总数 (过滤前)。
            temperature: LLM 温度 (越低越专注)。
            max_tokens: 最大输出令牌数。

        返回:
            包含键: summary (str), sections (dict), stats (dict) 的字典。
        """
        # 步骤 1: 格式化消息用于提示词
        formatted = format_messages_for_prompt(messages)

        # 步骤 2: 构建提示词
        user_prompt = SUMMARY_USER_TEMPLATE.format(
            chat_name=chat_name or "公司聊天",
            hours=hours_back,
            total_count=total_count,
            important_count=len(messages),
            message_list=formatted,
        )

        llm_messages = [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 步骤 3: 调用 LLM
        try:
            resp = await self._chat(
                messages=llm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            summary_text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:
            logger.exception("LLM 摘要生成失败")
            # 回退: 从评分消息构建简单摘要
            summary_text = _build_fallback_summary(messages, chat_name, hours_back)
            return {
                "summary": summary_text,
                "sections": {},
                "stats": {
                    "total_messages": total_count,
                    "important_messages": len(messages),
                    "fallback": True,
                    "error": str(exc),
                },
            }

        # 步骤 4: 从 LLM 输出解析部分
        sections = _parse_sections(summary_text)

        # 步骤 5: 构建统计信息
        stats = _build_stats(messages, total_count, hours_back)

        return {
            "summary": summary_text,
            "sections": sections,
            "stats": stats,
        }


# ============================================================
# 输出解析
# ============================================================

def _parse_sections(summary_text: str) -> Dict[str, str]:
    """将 LLM 输出解析为结构化部分。

    在部分标记如 [通知]、[任务] 等处分割。
    如果解析失败，将整个文本放在 "raw" 键下。

    参数:
        summary_text: 原始 LLM 输出。

    返回:
        映射部分名称到内容字符串的字典。
    """
    import re

    sections: Dict[str, str] = {}
    # 已知部分标记
    markers = [
        ("notification", r"\[通知\]"),
        ("task", r"\[任务\]"),
        ("meeting", r"\[会议\]"),
        ("risk", r"\[风险\]"),
        ("other", r"\[其他\]"),
    ]

    remaining = summary_text
    for i, (key, pattern) in enumerate(markers):
        match = re.search(pattern, remaining, re.IGNORECASE)
        if not match:
            sections[key] = ""
            continue

        start = match.end()
        # 查找下一个标记或文本结尾
        next_start = len(remaining)
        for _, next_pattern in markers[i + 1:]:
            next_match = re.search(next_pattern, remaining[start:], re.IGNORECASE)
            if next_match:
                next_start = start + next_match.start()
                break

        content = remaining[start:next_start].strip()
        # 清理: 移除前后空白和要点符号
        sections[key] = content
        remaining = remaining[next_start:]

    # 如果没有解析到任何部分，将所有内容放在 "raw" 下
    if not any(sections.values()):
        sections["raw"] = summary_text

    return sections


def _build_stats(
    messages: List[ScoredMessage],
    total_count: int,
    hours_back: int,
) -> Dict[str, Any]:
    """从评分消息构建摘要统计信息。

    包含: 各类别消息计数、时间范围、热门关键词。
    """
    categories: Dict[str, int] = {}
    senders: Dict[str, int] = {}
    top_kws: Dict[str, int] = {}

    for sm in messages:
        categories[sm.category] = categories.get(sm.category, 0) + 1
        if sm.sender_name:
            senders[sm.sender_name] = senders.get(sm.sender_name, 0) + 1
        for kw in sm.matched_keywords:
            top_kws[kw] = top_kws.get(kw, 0) + 1

    # 排序并限制热门关键词
    sorted_kws = sorted(top_kws.items(), key=lambda x: -x[1])[:10]

    # 时间范围
    times = [sm.create_time for sm in messages if sm.create_time]
    time_range = ""
    if times:
        t_min = min(times)
        t_max = max(times)
        time_range = f"{t_min.strftime('%m-%d %H:%M')} ~ {t_max.strftime('%H:%M')}"

    return {
        "total_messages": total_count,
        "important_messages": len(messages),
        "hours_back": hours_back,
        "categories": categories,
        "active_senders": len(senders),
        "top_senders": sorted(senders.items(), key=lambda x: -x[1])[:5],
        "top_keywords": sorted_kws,
        "time_range": time_range,
    }


def _build_fallback_summary(
    messages: List[ScoredMessage],
    chat_name: str,
    hours_back: int,
) -> str:
    """当 LLM 不可用时构建简单摘要。

    按类别分组消息并列出前几项。
    这是一个降级策略，不是主要路径。
    """
    if not messages:
        return f"最近 {hours_back} 小时内未找到重要消息。"

    lines = [
        f"聊天: {chat_name or '公司聊天'}",
        f"时间: 最近 {hours_back}h, {len(messages)} 条重要消息",
        "",
    ]

    # 按类别分组
    from collections import defaultdict
    by_cat: Dict[str, List[ScoredMessage]] = defaultdict(list)
    for sm in messages:
        by_cat[sm.category].append(sm)

    cat_order = ["notification", "risk", "meeting", "task", "other"]
    cat_labels = {
        "notification": "[通知]",
        "risk": "[风险/事故]",
        "meeting": "[会议]",
        "task": "[任务]",
        "other": "[其他]",
    }

    for cat in cat_order:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(cat_labels.get(cat, f"[{cat}]"))
        for sm in items[:5]:
            text = sm.plain_text[:120]
            lines.append(f"  - [{sm.time_str}] {sm.sender_name}: {text}")
        lines.append("")

    return "\n".join(lines)
