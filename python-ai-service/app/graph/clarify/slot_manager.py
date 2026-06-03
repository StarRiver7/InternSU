import json, re
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger
logger = get_logger(__name__)

SLOT_SCHEMAS = {
    "sql_query": [
        {"name": "department", "label": "department scope", "required": True, "type": "str", "hint": "all / dept name"},
        {"name": "time_range", "label": "time range", "required": True, "type": "str", "hint": "today / this week / this month"},
        {"name": "metric", "label": "metric", "required": True, "type": "str", "hint": "count / amount / orders"},
        {"name": "include_inactive", "label": "include inactive", "required": False, "type": "bool", "default": False},
    ],
    "rag_query": [
        {"name": "topic", "label": "topic", "required": True, "type": "str", "hint": "travel / onboarding / attendance"},
        {"name": "kb_scope", "label": "kb scope", "required": False, "type": "str", "default": "public"},
    ],
}


class SlotManager:
    @staticmethod
    def get_slots(intent):
        return SLOT_SCHEMAS.get(intent, [])

    @staticmethod
    def check_missing(slots, collected):
        missing = []
        for s in slots:
            if s.get("required") and s["name"] not in collected:
                missing.append(s["name"])
        return missing

    @staticmethod
    def get_slot_info(slot_name, slots):
        for s in slots:
            if s["name"] == slot_name:
                return s
        return None

    @staticmethod
    async def extract_slots_from_response(user_response, slots, previous_question=""):
        if not slots:
            return {}
        slot_names = [s["name"] for s in slots]
        import json, re

        # Build context for LLM: describe what slots to look for
        slot_descs = []
        for s in slots:
            hint = s.get("hint", "")
            slot_descs.append(f"  - {s['name']} ({s.get('label', s['name'])}): {hint}")
        slot_context = "\n".join(slot_descs)

        system_msg = (
            "Extract slot values from the user's message.\n"
            "Return ONLY a JSON object with slot names as keys.\n"
            f"Slots to look for:\n{slot_context}\n"
            "If a slot value is not found, omit it. Never include null values.\n"
            "Example output: {\"topic\": \"onboarding\"}"
        )
        try:
            resp = await llm_gateway.chat(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Message: {user_response}"},
                ],
                temperature=0.0, max_tokens=256,
            )
            m = re.search(r"{[^}]+}", resp.content)
            if m:
                extracted = json.loads(m.group())
                return {k: v for k, v in extracted.items() if k in slot_names and v is not None}
        except Exception as e:
            logger.warning(f"[SlotManager] 槽位提取失败: {e}")
        return {}

slot_manager = SlotManager()
