"""记忆节点 — 每轮对话后持久化会话状态到 Redis。

【架构定位】
该节点是 LangGraph 工作流的最终节点之一（在 answer_node 之后），
负责将对话状态持久化到 Redis，为后续多轮对话提供上下文记忆。

【写入内容】
  1. 用户/助手消息到会话历史（用于后续上下文注入）
  2. 图状态快照（澄清状态、槽位等）用于状态恢复
  3. RAG 特定元数据（来源、引用）用于多轮 RAG 上下文

【多轮 RAG 支持场景】
  - 用户问"年假呢？" → 记忆提供"请假制度"上下文
  - 先前的引用信息影响后续搜索结果相关性

【设计要点】
  - 非阻塞：持久化失败不影响主流程（try-catch 吞掉异常）
  - 仅保存前 3 条 Source 文档，控制 Redis 存储体积
  - 图状态快照支持澄清中断后的任务恢复
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.memory.memory_manager import memory_manager
from app.core.logger import get_logger

logger = get_logger(__name__)


async def memory_node(state: InternState) -> InternState:
    """持久化对话轮到 Redis 记忆。

    【写入内容】
      1. 用户消息 + 助手回答 → 会话历史（add_message）
      2. 图状态快照 → 状态记忆（save_graph_state）
      3. RAG 元数据（来源、引用）→ 多轮上下文（record_turn）

    【状态读取】
      - user_id, conversation_id, user_message, final_answer, intent
      - source_documents, retrieved_docs 等 RAG 相关信息

    【容错设计】
      - 持久化失败不影响主流程，仅记录 Warning 日志
      - 保证对话核心流程的稳定性

    Args:
        state: LangGraph 工作流状态

    Returns:
        更新后的 state（仅更新 trace_steps）
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
        # 1. 记录对话回合到会话历史
        await memory_manager.add_message(user_id, conv_id, "user", user_msg)
        if assistant_msg:
            await memory_manager.add_message(user_id, conv_id, "assistant", assistant_msg)

        # 2. 保存图状态快照（用于澄清中断后的任务恢复）
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
            # 多轮 RAG 上下文
            "last_rag_query": state.get("retrieval_query", ""),
            "last_citation_count": state.get("citation_count", 0),
            "last_source_docs": state.get("source_documents", [])[:3],  # 【存储优化】仅保存前3条
        }
        await memory_manager.save_graph_state(user_id, conv_id, graph_state)

        # 3. 记录带有 RAG 元数据的回合
        sources = state.get("source_documents", [])
        await memory_manager.record_turn(
            user_id, conv_id, user_msg, assistant_msg,
            sources=sources,
            intent=intent,
        )

        duration_ms = int((time.time() - t0) * 1000)
        _finish_trace(state, "记忆已更新", t0)

        logger.debug(
            f"[MemoryNode] 已保存对话: 意图={intent}, "
            f"来源数={len(sources)}, 耗时={duration_ms}ms"
        )

    except Exception as e:
        # 【容错设计】持久化失败不影响主流程
        logger.warning(f"记忆保存失败（非阻塞）: {e}")
        _add_trace(state, "记忆更新暂时不可用，继续处理")

    return state


def _add_trace(state: InternState, message: str):
    """向状态中添加 trace 步骤。

    Args:
        state: LangGraph 工作流状态
        message: 步骤描述信息
    """
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "memory_node",
        "step_type": "memory",
        "step_name": "记忆持久化",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _finish_trace(state: InternState, message: str, t0: float):
    """完成 trace 步骤，记录耗时。

    Args:
        state: LangGraph 工作流状态
        message: 完成消息
        t0: 开始时间戳（用于计算耗时）
    """
    duration_ms = int((time.time() - t0) * 1000)
    if state.get("trace_steps"):
        state["trace_steps"][-1] = {
            "node": "memory_node",
            "step_type": "memory",
            "step_name": "记忆持久化",
            "message": message,
            "status": "completed",
            "duration_ms": duration_ms,
            "timestamp": _now(),
        }


def _now() -> str:
    """返回当前 UTC 时间（ISO 8601 格式）。
    
    Returns:
        UTC 时间字符串
    """
    return datetime.now(timezone.utc).isoformat()
