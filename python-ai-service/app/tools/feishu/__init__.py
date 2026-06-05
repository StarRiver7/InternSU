"""
Feishu Agent Module — Enterprise chat message summary.

Modules:
  feishu_client:           Feishu Open API client (token, chats, messages)
  feishu_message_filter:   Enterprise message importance scoring & filtering
  feishu_summary:          LLM prompt builder & structured summary generator
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
