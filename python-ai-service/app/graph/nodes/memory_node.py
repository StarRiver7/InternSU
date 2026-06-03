"""记忆节点 — 每轮对话后持久化会话状态到 Redis。

写入内容:
  - 用户/助手消息到会话历史
  - 图状态（澄清状态、槽位等）
  - RAG 特定元数据（使用的来源、引用）

支持多轮 RAG:
  - 用户问"年假呢？" → 记忆提供"请假制度"上下文
  - 先前的引用信息影响后续搜索
"""

import time
import json
from datetime import datetime, timezone

from app.graph.state import InternState
from app.memory.memory_manager import memory_manager
from app.core.logger import get_logger

logger = get_logger(__name__)


async def memory_node(state: InternState) -> InternState:
    """持久化对话轮到 Redis 记忆。

    记录内容:
      1. 用户消息 + 助手回答 → 会话历史
      2. 图状态快照（澄清、槽位、意图）→ 状态记忆
      3. RAG 元数据（来源、引用）→ 用于多轮上下文
    """
    t0 = time.time()
    state["current_node"] = "memory_node"

    _add_trace(state, "正在更新记忆...")

    user_id = state.get("user_id", "0")
    conv_id = state.get("conversation_id", "")
    user_msg = state.get("user_message", "")
    assistant_msg = state.get("final_answer", "")
    intent = state.get("intent", "chat")

    if not conv_id or not user_msg:
        _add_trace(state, "无会话信息，跳过记忆存储")
        return state

    try:
        # 1. Record the conversation turn
        await memory_manager.add_message(user_id, conv_id, "user", user_msg)
        if assistant_msg:
            await memory_manager.add_message(user_id, conv_id, "assistant", assistant_msg)

        # 2. Save graph state for potential restore
        graph_state = {
            "intent": intent,
            "intent_detail": state.get("intent_detail", intent),
            "clarify_pending": state.get("clarify_pending", False),
            "clarify_question": state.get("clarify_question", ""),
            "clarify_round": state.get("clarify_round", 0),
            "clarify_finished": state.get("clarify_finished", False),
            "collected_slots": state.get("collected_slots", {}),
            "space_ids": state.get("space_ids", []),
            "trust_level": state.get("trust_level", "medium"),
            # RAG context for multi-turn
            "last_rag_query": state.get("retrieval_query", ""),
            "last_citation_count": state.get("citation_count", 0),
            "last_source_docs": state.get("source_documents", [])[:3],
        }
        await memory_manager.save_graph_state(user_id, conv_id, graph_state)

        # 3. Record turn with RAG metadata
        sources = state.get("source_documents", [])
        await memory_manager.record_turn(
            user_id, conv_id, user_msg, assistant_msg,
            sources=sources,
            intent=intent,
        )

        duration_ms = int((time.time() - t0) * 1000)
        _finish_trace(state, "记忆已更新", t0)

        logger.debug(
            f"[MemoryNode] Saved turn: intent={intent}, "
            f"sources={len(sources)}, {duration_ms}ms"
        )

    except Exception as e:
        logger.warning(f"Memory save failed (non-blocking): {e}")
        _add_trace(state, "记忆更新暂时不可用，继续处理")

    return state


def _add_trace(state: InternState, message: str):
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "memory_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _finish_trace(state: InternState, message: str, t0: float):
    duration_ms = int((time.time() - t0) * 1000)
    if state.get("trace_steps"):
        state["trace_steps"][-1] = {
            "node": "memory_node",
            "message": message,
            "status": "completed",
            "duration_ms": duration_ms,
            "timestamp": _now(),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
