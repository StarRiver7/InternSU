import json
from app.memory.redis_client import redis_client
from app.memory.memory_keys import state_key, clarify_key, slots_key, TTL_STATE, TTL_CLARIFY, TTL_SLOTS
from app.core.logger import get_logger
logger = get_logger(__name__)

class StateMemory:
    async def save_state(self, user_id, conv_id, graph_state):
        if graph_state is None:
            logger.warning("save_state called with None graph_state, skipping")
            return
        data = {
            "intent": graph_state.get("intent"),
            "intent_confidence": graph_state.get("intent_confidence"),
            "clarify_required": graph_state.get("clarify_required"),
            "clarify_pending": graph_state.get("clarify_pending"),
            "clarify_round": graph_state.get("clarify_round"),
            "clarify_question": graph_state.get("clarify_question"),
            "pending_task": graph_state.get("pending_task"),
            "task_context": graph_state.get("task_context"),
            "clarify_finished": graph_state.get("clarify_finished"),
            "done": graph_state.get("done"),
        }
        s = json.dumps(data, ensure_ascii=False, default=str)
        key = state_key(user_id, conv_id)
        await redis_client.set(key, s, TTL_STATE)
        logger.debug(f"State saved: {user_id}/{conv_id}")

    async def load_state(self, user_id, conv_id):
        key = state_key(user_id, conv_id)
        raw = await redis_client.get(key)
        if raw:
            data = json.loads(raw)
            logger.debug(f"State loaded: {user_id}/{conv_id}")
            return data
        return {}

    async def save_clarify(self, user_id, conv_id, clarify_question, pending):
        data = json.dumps({"question": clarify_question, "pending": pending}, ensure_ascii=False)
        await redis_client.set(clarify_key(user_id, conv_id), data, TTL_CLARIFY)

    async def load_clarify(self, user_id, conv_id):
        raw = await redis_client.get(clarify_key(user_id, conv_id))
        if raw:
            return json.loads(raw)
        return {}

    async def save_slots(self, user_id, conv_id, slots):
        data = json.dumps(slots, ensure_ascii=False)
        await redis_client.set(slots_key(user_id, conv_id), data, TTL_SLOTS)

    async def load_slots(self, user_id, conv_id):
        raw = await redis_client.get(slots_key(user_id, conv_id))
        if raw:
            return json.loads(raw)
        return {}

    async def clear_all(self, user_id, conv_id):
        await redis_client.delete(state_key(user_id, conv_id), clarify_key(user_id, conv_id), slots_key(user_id, conv_id))
        logger.debug(f"State cleared: {user_id}/{conv_id}")

state_memory = StateMemory()
