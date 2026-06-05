"""
飞书代理模块 — 企业聊天消息摘要。

模块:
  feishu_client:           飞书开放 API 客户端 (令牌、聊天、消息)
  feishu_message_filter:   企业消息重要性评分与过滤
  feishu_summary:          LLM 提示词构建器与结构化摘要生成器
"""

from app.tools.feishu.feishu_client import (
    FeishuClient, FeishuMessage, ChatInfo, PaginatedResult, TokenCache,
)
from app.tools.feishu.feishu_message_filter import (
    MessageFilter, ScoredMessage, HIGH_IMPORTANCE_KEYWORDS,
)
from app.tools.feishu.feishu_summary import (
    FeishuSummaryGenerator, format_messages_for_prompt,
    SUMMARY_SYSTEM_PROMPT, SUMMARY_USER_TEMPLATE,
)

__all__ = [
    "FeishuClient", "FeishuMessage", "ChatInfo", "PaginatedResult", "TokenCache",
    "MessageFilter", "ScoredMessage", "HIGH_IMPORTANCE_KEYWORDS",
    "FeishuSummaryGenerator", "format_messages_for_prompt",
    "SUMMARY_SYSTEM_PROMPT", "SUMMARY_USER_TEMPLATE",
]
