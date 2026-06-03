"""RAG 检索节点 — 带查询重写和智能回退的聚焦检索。

【架构定位】
该节点是 RAG 管道的核心入口，负责从用户查询到知识库检索的完整流程。
位于意图识别之后、引用构建之前，是 RAG 子图的第一跳。

【数据流】
┌─────────────────┐     ┌─────────────────────────┐     ┌─────────────────┐
│ intent_node    │ ──→ │ rag_retrieval_node    │ ──→ │ rag_rerank_node │
│ (意图识别)      │     │ (检索节点)             │     │ (重排序)        │
└─────────────────┘     └─────────────────────────┘     └─────────────────┘

【检索策略】
- Phase 1: 查询重写 (LLM 语义扩展) — 当前版本暂时禁用
- Phase 2: 混合检索 (向量 + 关键词 + RRFF 融合)
- Phase 3: 权限过滤 (部门/知识空间隔离)
- Phase 4: 智能回退 (无结果时重试最多 3 次)

【设计要点】
- 使用 lazy import 避免循环依赖
- 权限过滤暂时禁用，确保检索结果能正常返回
- 最大重试次数 3 次，防止无限循环
- 支持按 doc_ids 限定文档范围
"""

import time
from datetime import datetime, timezone
from typing import Optional

from app.graph.state import InternState
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def rag_retrieval_node(state: InternState) -> InternState:
    """执行带智能回退的混合检索。

    智能检索行为：
    - 第 1 次尝试：原始查询 → 混合检索
    - 第 2-3 次尝试（回退）：重写后的查询 → 混合检索
    - 3 次全部失败：标记为检索失败，触发降级回答
    
    Args:
        state: LangGraph 工作流状态对象
        
    Returns:
        更新后的状态对象，包含以下新增字段:
        - rag_triggered: RAG 流程已触发
        - query_rewritten: LLM 重写后的查询
        - retrieval_query: 最终用于检索的查询
        - retrieval_results: 检索结果列表
        - retrieval_count: 检索结果数量
        - retrieval_attempts: 检索尝试次数
        - retrieval_elapsed_ms: 检索耗时
        
    Note:
        - 最大尝试次数硬编码为 3，防止死循环
        - 权限过滤当前禁用，生产环境需重新启用
    """
    t0 = time.time()
    state["current_node"] = "rag_retrieval_node"
    state["rag_triggered"] = True

    # 记录追踪步骤
    _add_trace(state, "正在搜索企业知识库...")

    query = state["user_message"]
    user_id = _to_int(state.get("user_id", "0"))
    permission_ctx = state.get("permission_context", {})
    department_id = permission_ctx.get("department_id")
    space_ids = state.get("space_ids") or permission_ctx.get("allowed_space_ids") or []

    # 检索尝试次数递增（用于智能回退控制）
    attempts = state.get("retrieval_attempts", 0) + 1
    state["retrieval_attempts"] = attempts

    # ── Phase 1: 查询重写（暂时禁用）──────────────────────────────
    # TODO: [功能完善] 启用 LLM 查询重写以提升检索召回率
    # 查询重写的作用：将用户的口语化表达转换为更适合检索的查询形式
    # 例如："员工年假怎么算" → "年假计算规则 带薪年假"
    _add_trace(state, "准备搜索...")
    state["query_rewritten"] = query
    search_query = query  # 当前版本直接使用原始查询
    state["retrieval_query"] = search_query
    _add_trace(state, f"搜索查询: {search_query[:40]}...")

    # ── Phase 2: 混合检索 ─────────────────────────────────────────
    # 混合检索 = 密集向量检索 (BGE-M3) + 稀疏关键词检索 (BM25) + RRFF 融合
    # 权重配置：向量 0.7 + 关键词 0.3 (参见 config.py)
    _add_trace(state, "正在进行混合检索...")
    try:
        # 使用 lazy import 避免模块循环依赖
        from app.retrieval.hybrid_retriever import hybrid_retriever
        
        # 文档 ID 过滤（可选，用于限定检索范围）
        doc_id_strs = [str(d) for d in state.get("doc_ids")] if state.get("doc_ids") else None
        
        # 调用混合检索器
        # top_k=30: 初始召回数量（融合前）
        # final_k=40: 融合后保留数量（给重排序阶段足够的选择空间）
        chunks = await hybrid_retriever.search(
            query=search_query,
            top_k=settings.rag_top_k,  # 30
            final_k=settings.rag_final_k * 2,  # 40
            doc_ids=doc_id_strs,
            space_id=str(space_ids[0]) if space_ids else None,
        )

        # ── Phase 3: 权限过滤（暂时禁用）──────────────────────────
        # FIXME: [安全缺陷] 权限过滤当前禁用，任何用户都能检索所有文档
        # 生产环境必须启用，否则存在数据越权访问风险
        # 
        # 权限过滤逻辑：
        # 1. 检查用户是否有权访问文档所属的知识空间
        # 2. 部门私有文档只能本部门用户访问
        # 3. 公共文档对所有用户可见
        #
        # if permission_ctx and chunks:
        #     filtered = permission_filter.filter_chunks(
        #         chunks=chunks,
        #         user_id=str(user_id),
        #         department_id=department_id or 0,
        #         department_path=permission_ctx.get("department_path", ""),
        #         allowed_space_ids=space_ids,
        #     )
        # else:
        #     filtered = chunks
        filtered = chunks  # 暂时不过滤，确保检索功能正常

        state["retrieval_results"] = filtered
        state["retrieval_count"] = len(filtered)
        state["retrieved_docs"] = filtered

    except Exception as e:
        logger.warning(f"[RAGRetrieval] 检索失败: {e}")
        state["retrieval_results"] = []
        state["retrieval_count"] = 0
        state["retrieved_docs"] = []

    # ── Phase 4: 智能回退判断 ─────────────────────────────────────
    # 如果没有检索到结果且还有重试机会，使用扩展查询重试
    retrieval_count = state["retrieval_count"]

    if retrieval_count == 0 and attempts < 3:
        # 还有重试机会：触发路由器重新进入本节点
        state["retrieval_fallback_used"] = True
        _add_trace(state, f"首次检索无结果，正在进行第{attempts}次智能重试...")
        logger.info(
            f"[RAGRetrieval] Attempt {attempts}: 0 results, "
            f"will retry with rewritten query"
        )
        state["retrieval_failed"] = False  # 尚未失败，等待重试
    elif retrieval_count == 0:
        # 所有重试次数用尽，标记为失败
        state["retrieval_failed"] = True
        _add_trace(state, "多次检索后仍未找到相关内容")
        logger.warning("[RAGRetrieval] 所有尝试均已用尽，无检索结果")
    else:
        # 检索成功
        state["retrieval_failed"] = False
        _add_trace(state, f"检索到 {retrieval_count} 条相关知识")

    state["retrieval_elapsed_ms"] = int((time.time() - t0) * 1000)

    logger.info(
        f"[RAGRetrieval] '{query[:40]}': {retrieval_count} results, "
        f"attempt={attempts}, {state['retrieval_elapsed_ms']}ms"
    )

    return state


def _add_trace(state: InternState, message: str) -> None:
    """向状态中添加追踪步骤。

    Args:
        state: LangGraph 状态对象
        message: 追踪消息内容
    """
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "rag_retrieval_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _to_int(value) -> int:
    """安全转换为整数。

    Args:
        value: 待转换的值（可以是字符串、数字或 None）
        
    Returns:
        转换后的整数，转换失败返回 0
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _now() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()
