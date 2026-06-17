"""
FeishuTool — 飞书总结代理的 BaseTool 适配器

将飞书消息总结管道（获取 + 过滤 + 提示词 + LLM）包装到 BaseTool 接口中。

使用方法:
    tool = FeishuTool()
    registry.register(tool)
    result = await manager.execute("feishu_summary", {"chat_id": "oc_xxx"})
"""

import logging
import time
from typing import Any, Dict, Optional

from app.tools.base import BaseTool, ToolMetadata, ToolParameter, ToolResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class FeishuTool(BaseTool):
    """飞书群消息总结工具。

    从飞书群聊获取最近消息，筛选重要消息，并生成结构化的 LLM 摘要，包含以下部分：
    通知、任务、会议、风险、其他。

    处理流程:
      1. FEISHU_QUERY — 通过 FeishuClient 获取消息
      2. MESSAGE_FILTER — 评分并筛选重要消息
      3. PROMPT_BUILD — 构建结构化摘要提示词
      4. LLM_GENERATION — 通过 LLM 生成摘要
    """

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="feishu_agent",
            display_name="飞书群消息总结",
            description=(
                "总结飞书群聊中的近期消息。自动拉取消息、筛选重要内容、"
                "生成结构化摘要（通知/任务/会议/风险/其他）。"
                "示例: '总结技术群最近24小时的消息'"
            ),
            category="feishu",
            version="2.0.0",
            timeout_seconds=90,
            enabled=True,
            parameters=[
                ToolParameter(
                    name="chat_id",
                    type="string",
                    description="群聊ID（可选，不填则自动选择第一个群）",
                    required=False,
                ),
                ToolParameter(
                    name="hours",
                    type="integer",
                    description="回溯时间（小时，默认24）",
                    required=False,
                    default=24,
                ),
                ToolParameter(
                    name="max_messages",
                    type="integer",
                    description="最大拉取消息数（默认100）",
                    required=False,
                    default=100,
                ),
            ],
        )

    async def _execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行飞书消息总结管道。

        参数:
            params: 可选 'chat_id', 'hours'（默认24）, 'max_messages'（默认100）。

        返回:
            ToolResult，包含结构化摘要。
        """
        import time as _time
        t_start = _time.time()
        trace_steps: list = []
        chat_id: Optional[str] = params.get("chat_id")
        hours: int = params.get("hours", 24)
        max_messages: int = params.get("max_messages", 100)

        # ---- 阶段 1: FEISHU_QUERY ----
        t1 = _time.time()
        trace_steps.append({
            "step_type": "feishu_query",
            "step_name": "飞书消息获取",
            "message": "正在获取飞书消息...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.tools.feishu.feishu_client import FeishuClient

            client = FeishuClient(
                app_id=settings.feishu_app_id,
                app_secret=settings.feishu_app_secret,
                base_url=settings.feishu_base_url,
                token_cache_ttl=settings.feishu_token_cache_ttl,
                default_page_size=settings.feishu_default_page_size,
                max_retries=settings.feishu_max_retries,
                request_timeout=settings.feishu_request_timeout,
            )

            # 解析 chat_id
            if not chat_id:
                chats_result = await client.list_chats(page_size=20)
                if not chats_result.items:
                    await client.close()
                    return ToolResult(
                        success=False,
                        error="未找到飞书群聊，请先将机器人添加到群聊中。",
                        trace_steps=trace_steps,
                    )
                chat_id = chats_result.items[0].chat_id
                chat_name = chats_result.items[0].name or f"Chat-{chat_id[:8]}"
            else:
                chat_name = f"Chat-{chat_id[:8]}"

            # 获取消息
            messages = await client.fetch_messages_for_summary(
                chat_id=chat_id,
                lookback_hours=hours,
                max_messages=max_messages,
            )
            total_count = len(messages)
            await client.close()

            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t1) * 1000)
            trace_steps[-1]["detail"] = {
                "chat_id": chat_id, "chat_name": chat_name,
                "total": total_count, "hours": hours,
            }
            trace_steps[-1]["message"] = f"从 {chat_name} 获取了 {total_count} 条消息"

        except ValueError as exc:
            trace_steps[-1]["status"] = "failed"
            trace_steps[-1]["detail"] = {"error": str(exc)}
            return ToolResult(
                success=False,
                error=f"飞书未配置：{exc}。请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET。",
                trace_steps=trace_steps,
            )
        except Exception as exc:
            logger.exception("Feishu fetch failed")
            trace_steps[-1]["status"] = "failed"
            return ToolResult(
                success=False,
                error=f"获取飞书消息失败：{exc}",
                trace_steps=trace_steps,
            )

        if total_count == 0:
            return ToolResult(
                success=True,
                data={"chat_name": chat_name, "total": 0},
                summary=f"在最近 {hours} 小时内未找到 '{chat_name}' 的消息。",
                trace_steps=trace_steps,
            )

        # ---- 阶段 2: MESSAGE_FILTER ----
        t2 = _time.time()
        trace_steps.append({
            "step_type": "message_filter",
            "step_name": "消息重要性筛选",
            "message": "正在筛选重要消息...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.tools.feishu.feishu_message_filter import MessageFilter
            filt = MessageFilter(max_results=50)
            scored = filt.filter_and_score(messages)
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t2) * 1000)
            trace_steps[-1]["detail"] = {
                "total": total_count, "important": len(scored),
                "categories": self._count_categories(scored),
            }
        except Exception as exc:
            logger.exception("Message filter failed")
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["detail"] = {"error": str(exc), "fallback": True}
            # 降级：将所有消息视为已评分
            from app.tools.feishu.feishu_message_filter import ScoredMessage
            scored = [
                ScoredMessage(
                    message_id=m.message_id,
                    sender_name=m.sender_name or "unknown",
                    plain_text=m.plain_text,
                    create_time=m.create_time,
                    score=1, category="other",
                )
                for m in messages[:50]
            ]

        # ---- 阶段 3: PROMPT_BUILD ----
        t3 = _time.time()
        trace_steps.append({
            "step_type": "prompt_build",
            "step_name": "提示词构建",
            "message": "正在构建摘要提示...",
            "status": "running",
            "timestamp": _now(),
        })
        from app.tools.feishu.feishu_summary import (
            format_messages_for_prompt,
            SUMMARY_SYSTEM_PROMPT, SUMMARY_USER_TEMPLATE,
        )
        formatted = format_messages_for_prompt(scored)
        user_prompt = SUMMARY_USER_TEMPLATE.format(
            chat_name=chat_name, hours=hours,
            total_count=total_count, important_count=len(scored),
            message_list=formatted,
        )
        trace_steps[-1]["status"] = "completed"
        trace_steps[-1]["duration_ms"] = int((_time.time() - t3) * 1000)
        trace_steps[-1]["detail"] = {"prompt_chars": len(user_prompt)}

        # ---- 阶段 4: LLM_GENERATION ----
        t4 = _time.time()
        trace_steps.append({
            "step_type": "llm_generation",
            "step_name": "大模型摘要生成",
            "message": "正在使用大模型生成摘要...",
            "status": "running",
            "timestamp": _now(),
        })
        try:
            from app.llm.gateway import llm_gateway
            resp = await llm_gateway.chat(
                [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3, max_tokens=1200,
            )
            summary_text = resp.content if hasattr(resp, "content") else str(resp)
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["duration_ms"] = int((_time.time() - t4) * 1000)
            trace_steps[-1]["detail"] = {
                "input_tokens_est": len(user_prompt) // 2,
                "output_tokens_est": len(summary_text) // 2,
            }
        except Exception as exc:
            logger.exception("LLM summary failed")
            trace_steps[-1]["status"] = "completed"
            trace_steps[-1]["detail"] = {"error": str(exc), "fallback": True}
            # 降级摘要
            from app.tools.feishu.feishu_summary import _build_fallback_summary
            summary_text = _build_fallback_summary(scored, chat_name)

        return ToolResult(
            success=True,
            data={
                "chat_name": chat_name,
                "total_messages": total_count,
                "important_messages": len(scored),
            },
            summary=summary_text,
            trace_steps=trace_steps,
            token_usage={
                "input": len(user_prompt) // 2,
                "output": len(summary_text) // 2,
            },
        )

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------
    @staticmethod
    def _count_categories(scored: list) -> dict:
        cats: dict = {}
        for sm in scored:
            cats[sm.category] = cats.get(sm.category, 0) + 1
        return cats


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()