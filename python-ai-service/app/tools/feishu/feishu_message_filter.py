"""
飞书消息过滤器 — 企业消息重要性评分和过滤。

过滤原始聊天消息以提取重要消息，基于:
  - 关键词匹配 (通知、发布、会议、风险等)
  - @所有人 标签权重
  - 时间临近权重
  - 相似消息去重

由飞书摘要代理使用，在 LLM 摘要前减少噪音。
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 重要性关键词配置
# ============================================================

# 高重要性关键词及其权重 (用于评分)
HIGH_IMPORTANCE_KEYWORDS: Dict[str, int] = {
    # 通知与公告
    "通知": 10,
    "公告": 10,
    "重要": 8,
    "请注意": 8,
    "提醒": 7,

    # 发布与部署
    "上线": 9,
    "发布": 9,
    "部署": 8,
    "发版": 8,
    "灰度": 7,
    "回滚": 8,

    # 会议
    "会议": 8,
    "开会": 8,
    "评审": 7,
    "周会": 7,
    "站会": 6,
    "复盘": 7,

    # 截止日期与紧急
    "截止": 9,
    "紧急": 10,
    "尽快": 7,
    "DDL": 8,
    "deadline": 8,

    # 风险与事故
    "风险": 9,
    "故障": 10,
    "事故": 10,
    "告警": 9,
    "报警": 9,
    "Bug": 8,
    "bug": 8,
    "异常": 7,
    "报错": 8,
    "崩溃": 9,
    "宕机": 10,

    # 任务与需求
    "任务": 7,
    "需求": 7,
    "排期": 7,
    "负责人": 6,
    "进度": 6,
    "TODO": 6,
    "todo": 6,
    "待办": 6,

    # 决策与结论
    "结论": 8,
    "决定": 8,
    "确认": 6,
    "方案": 6,
}

# @所有人 提及权重加成
AT_EVERYONE_WEIGHT: int = 15

# 时间临近奖励:
# 最近几小时内的消息获得奖励分数 (时间偏好)
RECENCY_WINDOW_HOURS: int = 4
RECENCY_BONUS: int = 5

# 被视为"重要"的最低分数
# NOTE: 降低阈值以包含更多消息（原值 8 导致普通对话全部被过滤）
IMPORTANCE_THRESHOLD: int = 0

# 返回的最大重要消息数 (防止 LLM 令牌溢出)
MAX_IMPORTANT_MESSAGES: int = 50


# ============================================================
# 数据模型
# ============================================================

@dataclass
class ScoredMessage:
    """带有重要性分数和元数据的消息。

    属性:
        message_id: 飞书消息 ID。
        sender_name: 发送者显示名称。
        plain_text: 提取的纯文本内容。
        create_time: 消息发送时间。
        score: 计算的重要性分数 (越高越重要)。
        matched_keywords: 匹配的关键词 (用于调试)。
        is_at_everyone: 消息是否 @所有人。
        category: 检测到的类别 (通知/会议/任务/风险/其他)。
    """
    message_id: str
    sender_name: str
    plain_text: str
    create_time: Optional[datetime] = None
    score: int = 0
    matched_keywords: List[str] = field(default_factory=list)
    is_at_everyone: bool = False
    category: str = "other"

    @property
    def time_str(self) -> str:
        """用于提示显示的格式化时间字符串。"""
        if self.create_time:
            return self.create_time.strftime("%m-%d %H:%M")
        return ""


# ============================================================
# 消息过滤器
# ============================================================

class MessageFilter:
    """企业消息重要性过滤器。

    基于关键词匹配、@所有人 检测和时间临近度对消息评分。
    返回按分数排序的前 N 条重要消息。

    用法:
        filt = MessageFilter()
        scored = filt.filter_and_score(messages, max_results=50)
    """

    def __init__(
        self,
        keywords: Optional[Dict[str, int]] = None,
        threshold: int = IMPORTANCE_THRESHOLD,
        max_results: int = MAX_IMPORTANT_MESSAGES,
    ):
        """使用可配置的关键词权重初始化过滤器。

        参数:
            keywords: 关键词到权重的映射 (默认为内置)。
            threshold: 被视为重要的最低分数。
            max_results: 返回的最大重要消息数。
        """
        self._keywords = keywords or HIGH_IMPORTANCE_KEYWORDS
        self._threshold = threshold
        self._max_results = max_results

        # 预编译关键词正则模式以提高匹配效率
        # 按长度降序排序以优先匹配更长的关键词
        sorted_kws = sorted(self._keywords.keys(), key=len, reverse=True)
        self._pattern = re.compile(
            "|".join(re.escape(kw) for kw in sorted_kws),
            re.IGNORECASE,
        )

    # ----------------------------------------------------------
    # 主流程
    # ----------------------------------------------------------
    def filter_and_score(
        self,
        messages: List[Any],
        reference_time: Optional[datetime] = None,
        max_results: Optional[int] = None,
    ) -> List[ScoredMessage]:
        """评分和过滤消息，返回最重要的消息。

        流程:
          1. 对每条消息评分 (关键词 + @所有人 + 时间临近)
          2. 分类到类别
          3. 按阈值过滤
          4. 按分数降序排序
          5. 返回前 N 条

        参数:
            messages: FeishuMessage 对象列表。
            reference_time: 时间临近奖励的参考时间 (默认为当前)。
            max_results: 覆盖最大结果限制。

        返回:
            按重要性分数降序排序的 ScoredMessage 列表。
        """
        if reference_time is None:
            reference_time = datetime.now()
        limit = max_results or self._max_results

        # 步骤 1: 对每条消息评分
        scored: List[ScoredMessage] = []
        for msg in messages:
            sm = self._score_one(msg, reference_time)
            logger.debug(
                "MessageFilter: score=%d, threshold=%d, sender=%s, text=%s",
                sm.score, self._threshold, sm.sender_name,
                sm.plain_text[:50] if sm.plain_text else "(empty)",
            )
            if sm.score >= self._threshold:
                scored.append(sm)

        if not scored:
            logger.info("MessageFilter: no messages above threshold %d", self._threshold)
            return []

        # 步骤 2: 按分数降序排序，然后对相同分数按时间降序排序
        scored.sort(
            key=lambda m: (
                -m.score,
                -(m.create_time.timestamp() if m.create_time else 0),
            )
        )

        # 步骤 3: 去重近似重复的消息
        # (同一发送者 + 5 分钟内相似内容 → 保留最高分数)
        deduped = self._deduplicate(scored)

        result = deduped[:limit]
        logger.info(
            "MessageFilter: %d messages scored, %d above threshold, %d returned",
            len(messages), len(scored), len(result),
        )
        return result

    # ----------------------------------------------------------
    # 单条消息评分
    # ----------------------------------------------------------
    def _score_one(self, msg: Any, ref_time: datetime) -> ScoredMessage:
        """对单条消息评分。

        评分组成:
          1. 关键词匹配: 匹配关键词的权重总和
          2. @所有人 加成: 如果消息 @所有人 则加 AT_EVERYONE_WEIGHT
          3. 时间临近奖励: 如果在最近窗口内则加 RECENCY_BONUS
        """
        # 提取文本和元数据
        plain_text = getattr(msg, "plain_text", "") or ""
        sender = getattr(msg, "sender_name", "") or "unknown"
        msg_id = getattr(msg, "message_id", "") or ""
        create_time = getattr(msg, "create_time", None)
        content = getattr(msg, "content", "") or ""

        # 组成部分 1: 关键词匹配
        # 查找所有唯一关键词匹配并累加权重
        matched_kws: List[str] = []
        score = 0
        # 使用正则 finditer 进行高效的多关键词匹配
        for match in self._pattern.finditer(plain_text):
            kw = match.group()
            # 规范化大小写以查找权重
            kw_lower = kw.lower()
            # 先尝试精确大小写，再尝试小写
            weight = self._keywords.get(kw) or self._keywords.get(kw_lower)
            if weight and kw not in matched_kws:
                matched_kws.append(kw)
                score += weight

        # 也检查内容 JSON 中的 @所有人 和卡片文本中的关键词
        if not matched_kws and content:
            for match in self._pattern.finditer(content):
                kw = match.group()
                kw_lower = kw.lower()
                weight = self._keywords.get(kw) or self._keywords.get(kw_lower)
                if weight and kw not in matched_kws:
                    matched_kws.append(kw)
                    score += weight

        # 组成部分 2: @所有人 检测
        is_at_everyone = "@everyone" in content or "@所有人" in plain_text
        if is_at_everyone:
            score += AT_EVERYONE_WEIGHT
            if "@所有人" not in matched_kws:
                matched_kws.append("@所有人")

        # 组成部分 3: 时间临近奖励
        # 最近窗口内的消息获得额外权重
        if create_time and (ref_time - create_time) < timedelta(hours=RECENCY_WINDOW_HOURS):
            score += RECENCY_BONUS

        # 从匹配关键词确定类别
        category = self._classify(matched_kws)

        return ScoredMessage(
            message_id=msg_id,
            sender_name=sender,
            plain_text=plain_text,
            create_time=create_time,
            score=score,
            matched_keywords=matched_kws,
            is_at_everyone=is_at_everyone,
            category=category,
        )

    # ----------------------------------------------------------
    # 类别分类
    # ----------------------------------------------------------
    @staticmethod
    def _classify(matched_keywords: List[str]) -> str:
        """根据匹配关键词将消息分类到类别。

        优先级: 风险 > 通知 > 会议 > 任务 > 其他
        """
        kw_set = {k.lower() for k in matched_keywords}

        risk_kws = {"故障", "事故", "告警", "报警", "风险", "紧急", "崩溃", "宕机", "回滚"}
        notify_kws = {"通知", "公告", "重要", "请注意", "提醒", "@所有人"}
        meeting_kws = {"会议", "开会", "评审", "周会", "站会", "复盘"}
        task_kws = {"任务", "需求", "排期", "负责人", "进度", "todo", "待办", "ddl", "deadline", "截止"}
        release_kws = {"上线", "发布", "部署", "发版", "灰度"}

        if kw_set & risk_kws:
            return "risk"
        if kw_set & release_kws:
            return "notification"
        if kw_set & notify_kws:
            return "notification"
        if kw_set & meeting_kws:
            return "meeting"
        if kw_set & task_kws:
            return "task"
        return "other"

    # ----------------------------------------------------------
    # 去重
    # ----------------------------------------------------------
    @staticmethod
    def _deduplicate(
        scored: List[ScoredMessage],
        time_window_minutes: int = 5,
    ) -> List[ScoredMessage]:
        """移除近似重复的消息。

        同一发送者在 time_window_minutes 内的两条消息
        被视为重复；保留分数更高的那条。

        这可以防止同一公告被多人重复发送
        而占据摘要的大部分内容。
        """
        if len(scored) <= 1:
            return scored

        result: List[ScoredMessage] = []
        # 跟踪 (发送者, 时间桶) 对
        seen: Dict[Tuple[str, int], ScoredMessage] = {}

        for sm in scored:
            if not sm.create_time:
                result.append(sm)
                continue

            sender = sm.sender_name or "unknown"
            # 将时间分桶到 N 分钟窗口
            bucket = int(sm.create_time.timestamp() / (time_window_minutes * 60))
            key = (sender, bucket)

            if key in seen:
                # 保留分数更高的那条
                if sm.score > seen[key].score:
                    # 替换: 移除旧的，添加新的
                    try:
                        result.remove(seen[key])
                    except ValueError:
                        pass
                    result.append(sm)
                    seen[key] = sm
            else:
                result.append(sm)
                seen[key] = sm

        return result
