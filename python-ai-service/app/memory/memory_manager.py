import json, uuid
from datetime import datetime
from app.memory.redis_client import redis_client
from app.memory.state_memory import state_memory
from app.memory.memory_keys import session_key, conv_list_key, TTL_SESSION, TTL_CONV_LIST
from app.core.config import settings
from app.core.logger import get_logger
logger = get_logger(__name__)

class MemoryManager:
    def __init__(self):
        self._window = settings.conversation_window

    async def get_history(self, user_id, conv_id):
        try:
            raw = await redis_client.get(session_key(user_id, conv_id))
            return json.loads(raw) if raw else []
        except Exception as e:
            logger.warning(f"获取历史记录失败: {e}")
            return []

    async def add_message(self, user_id, conv_id, role, content):
        try:
            key = session_key(user_id, conv_id)
            history = await self.get_history(user_id, conv_id)
            history.append({"role": role, "content": content})
            max_len = self._window * 2
            if len(history) > max_len:
                history = history[-max_len:]
            await redis_client.set(key, json.dumps(history, ensure_ascii=False), TTL_SESSION)
            await self._update_conv_list(user_id, conv_id)
        except Exception as e:
            logger.warning(f"添加消息失败: {e}")

    async def _update_conv_list(self, user_id, conv_id, title=""):
        try:
            raw = await redis_client.hget(conv_list_key(), user_id)
            convs = json.loads(raw) if raw else []
            now = datetime.now().isoformat()
            for c in convs:
                if c.get("conversation_id") == conv_id:
                    c["updated_at"] = now
                    break
            else:
                convs.insert(0, {"conversation_id": conv_id, "title": title or "New", "created_at": now, "updated_at": now})
            await redis_client.hset(conv_list_key(), user_id, json.dumps(convs[:50], ensure_ascii=False))
            await redis_client.expire(conv_list_key(), TTL_CONV_LIST)
        except Exception as e:
            logger.warning(f"更新会话列表失败: {e}")

    async def clear(self, user_id, conv_id):
        await redis_client.delete(session_key(user_id, conv_id))
        await state_memory.clear_all(user_id, conv_id)

    async def list_conversations(self, user_id):
        try:
            raw = await redis_client.hget(conv_list_key(), user_id)
            return json.loads(raw) if raw else []
        except Exception:
            return []

    def generate_conversation_id(self):
        return uuid.uuid4().hex[:16]

    async def start_conversation(self, user_id, title=""):
        conv_id = self.generate_conversation_id()
        await self._update_conv_list(user_id, conv_id, title)
        return conv_id

# ---- Agent state save/restore ----

    async def save_graph_state(self, user_id, conv_id, graph_state):
        if graph_state is None:
            return
        await state_memory.save_state(user_id, conv_id, graph_state)
        slots = graph_state.get("collected_slots", {})
        if slots:
            await state_memory.save_slots(user_id, conv_id, slots)
        if graph_state.get("clarify_pending"):
            q = graph_state.get("clarify_question", "")
            await state_memory.save_clarify(user_id, conv_id, q, True)

    async def restore_graph_state(self, user_id, conv_id):
        state = await state_memory.load_state(user_id, conv_id)
        if state:
            slots = await state_memory.load_slots(user_id, conv_id)
            clarify = await state_memory.load_clarify(user_id, conv_id)
            state["collected_slots"] = slots
            if clarify.get("pending"):
                state["clarify_pending"] = True
            logger.info(f"State restored: clarify_pending={state.get("clarify_pending")}, slots={list(slots.keys())}")
        return state or {}

    async def record_turn(self, user_id, conv_id, user_msg, assistant_msg, sources=None, intent=None):
        await self.add_message(user_id, conv_id, "user", user_msg)
        await self.add_message(user_id, conv_id, "assistant", assistant_msg)
        await self._update_conv_list(user_id, conv_id)

memory_manager = MemoryManager()
