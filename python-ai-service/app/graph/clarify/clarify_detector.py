"""澄清检测器 — 判断用户查询是否需要进一步澄清。

【职责】
使用 LLM 分析用户消息，判断当前信息是否足够进行后续处理，
如果信息不足则触发澄清流程。

【使用场景】
  - 意图识别后，判断是否需要追问用户补充信息
  - 检查查询是否过于模糊或缺少必要参数

【返回值】
  - (True, {})：信息充足，可以继续
  - (False, {"reason": "..."})：信息不足，需要澄清
"""

import json
import re
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


async def check_info_sufficient(intent: str, user_message: str, history: list = None) -> tuple:
    """检查用户查询的信息是否足够进行后续处理。

    使用 LLM 判断当前消息是否包含足够的信息来执行对应意图的任务。

    Args:
        intent: 意图类型（chat/rag/sql等）
        user_message: 用户消息
        history: 对话历史（可选）

    Returns:
        (sufficient, data) 元组，其中：
        - sufficient: 是否信息充足
        - data: 包含判断理由的字典
    """
    # 聊天意图总是信息充足
    if intent == "chat":
        return True, {}

    # 构建检查消息
    msg = f"意图: {intent}。消息: {user_message}"

    try:
        resp = await llm_gateway.chat(
            [
                {"role": "system", "content": "判断信息是否充足。返回 JSON 格式: {sufficient: true/false, reason: 字符串}"},
                {"role": "user", "content": msg},
            ],
            temperature=0.0,
            max_tokens=128,
        )

        # 从响应中提取 JSON
        match = re.search(r"{[^}]+}", resp.content)
        if match:
            data = json.loads(match.group())
            return data.get("sufficient", True), data

    except Exception as e:
        logger.warning(f"[ClarifyDetector] 信息检查失败: {e}")

    # 默认认为信息充足
    return True, {}


# 全局实例
clarify_detector = check_info_sufficient
