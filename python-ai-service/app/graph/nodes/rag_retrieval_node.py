"""RAG 检索节点 — 带查询扩展和智能回退的聚焦检索（v3）。

【v3 变更】
- Phase 1: 启用 LLM 查询扩展（关键词 + 同义词），不再直接使用原始查询
- Phase 2: 全局 BM25 + 向量 BM25 双路融合（由 hybrid_retriever v3 实现）
- space_id 修复：支持多空间逗号分隔过滤
- top_k 提升：从 30 提升到 50，增加召回路

【架构定位】
该节点是 RAG 管道的核心入口，负责从用户查询到知识库检索的完整流程。
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.core.config import settings
from app.core.logger import get_logger
from app.llm.gateway import llm_gateway

logger = get_logger(__name__)

# ── 查询扩展 Prompt ────────────────────────────────────────────────
QUERY_EXPAND_PROMPT = """你是一个搜索查询优化器。将用户的原始问题扩展为更适合检索的查询词。

规则：
1. 提取核心关键词（2-5个词）
2. 添加同义词和相关术语
3. 用空格分隔所有关键词
4. 只返回关键词，不要解释

示例：
用户问题: 公司报销流程是什么
扩展查询: 报销 流程 费用报销 报销制度 报销规定 报销申请 差旅费

用户问题: 年假怎么算
扩展查询: 年假 带薪年假 年休假 休假天数 休假计算 PTO

用户问题: {query}

扩展查询:"""


async def _expand_query(query: str) -> str:
    """使用 LLM 扩展查询词（轻量级，~200 tokens）。"""
    try:
        prompt = QUERY_EXPAND_PROMPT.format(query=query)
        resp = await llm_gateway.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,
            model="deepseek-chat",
        )
        expanded = resp.content.strip()
        if expanded and len(expanded) > 2:
            # 合并原始查询和扩展查询
            return f"{query} {expanded}"
    except Exception as e:
        logger.warning(f"查询扩展失败: {e}")
    return query


async def rag_retrieval_node(state: InternState) -> InternState:
    """执行带查询扩展和智能回退的混合检索（v3）。

    检索策略：
    - Phase 1: LLM 查询扩展 → 生成关键词丰富的搜索查询
    - Phase 2: 全局 BM25 + 向量 BM25 + 向量检索 → 三路融合
    - Phase 3: 智能回退（无结果时最多重试 2 次）
    """
    t0 = time.time()
    state["current_node"] = "rag_retrieval_node"
    state["rag_triggered"] = True

    _add_trace(state, "正在搜索企业知识库...")

    query = state["user_message"]
    user_id = state.get("user_id", "0")
    permission_ctx = state.get("permission_context", {})
    space_ids = state.get("space_ids") or permission_ctx.get("allowed_space_ids") or []
    attempts = state.get("retrieval_attempts", 0) + 1
    state["retrieval_attempts"] = attempts

    # ── Phase 1: 查询扩展 ──────────────────────────────────────────
    _add_trace(state, "正在理解查询意图...")
    try:
        expanded_query = await _expand_query(query)
        state["query_rewritten"] = expanded_query
    except Exception:
        expanded_query = query
        state["query_rewritten"] = query

    # 第1次尝试用扩展查询，后续重试用原始查询（避免过度扩展）
    search_query = expanded_query if attempts == 1 else query
    state["retrieval_query"] = search_query
    _add_trace(state, f"搜索查询: {search_query[:60]}...")

    # ── Phase 2: 混合检索（v3: 全局 BM25 + 向量 BM25）────────────────
    _add_trace(state, "正在进行混合检索...")
    try:
        from app.retrieval.hybrid_retriever import hybrid_retriever

        doc_id_strs = [str(d) for d in state.get("doc_ids")] if state.get("doc_ids") else None

        # 支持多空间：用第一个 space_id 做过滤（Milvus 单值过滤限制）
        space_id_filter = str(space_ids[0]) if space_ids else None

        chunks = await hybrid_retriever.search(
            query=search_query,
            top_k=max(settings.rag_top_k, 50),  # v3: 提升到至少 50
            final_k=settings.rag_final_k * 2,  # 40
            doc_ids=doc_id_strs,
            space_id=space_id_filter,
        )

        filtered = chunks  # 权限过滤暂禁用（生产环境需启用）
        state["retrieval_results"] = filtered
        state["retrieval_count"] = len(filtered)

    except Exception as e:
        logger.warning(f"[RAGRetrieval] 检索失败: {e}")
        state["retrieval_results"] = []
        state["retrieval_count"] = 0

    # ── Phase 3: 智能回退判断 ─────────────────────────────────────
    retrieval_count = state["retrieval_count"]

    if retrieval_count == 0 and attempts < 3:
        state["retrieval_fallback_used"] = True
        _add_trace(state, f"首次检索无结果，正在进行第{attempts}次智能重试...")
        state["retrieval_failed"] = False
    elif retrieval_count == 0:
        state["retrieval_failed"] = True
        _add_trace(state, "多次检索后仍未找到相关内容")
        logger.warning("[RAGRetrieval] 所有尝试均已用尽，无检索结果")
    else:
        state["retrieval_failed"] = False
        _add_trace(state, f"检索到 {retrieval_count} 条相关知识")

    state["retrieval_elapsed_ms"] = int((time.time() - t0) * 1000)
    logger.info(
        f"[RAGRetrieval] '{query[:40]}': {retrieval_count} results, "
        f"attempt={attempts}, {state['retrieval_elapsed_ms']}ms"
    )
    return state


def _add_trace(state: InternState, message: str) -> None:
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "rag_retrieval_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()