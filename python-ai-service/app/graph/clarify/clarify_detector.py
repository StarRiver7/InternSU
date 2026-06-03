from app.llm.gateway import llm_gateway
from app.core.logger import get_logger
logger = get_logger(__name__)

async def check_info_sufficient(intent, user_message, history=None):
    if intent == "chat":
        return True, {}
    msg = "Intent: " + intent + ". Message: " + user_message
    try:
        resp = await llm_gateway.chat([{"role": "system", "content": "Decide if info is sufficient. Return JSON: {sufficient: true/false, reason: str}"}, {"role": "user", "content": msg}], temperature=0.0, max_tokens=128)
        import re
        m = re.search(r"{[^}]+}", resp.content)
        if m:
            data = json.loads(m.group())
            return data.get("sufficient", True), data
    except Exception as e:
        logger.warning(f"[ClarifyDetector] 信息检查失败: {e}")
    return True, {}

clarify_detector = check_info_sufficient
