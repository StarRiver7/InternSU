"""引用构建节点 — 从重排序结果构建结构化引用。

处理流程：rerank_results → CitationBuilder → CitationSet + 可信度评估

写入状态：citations, citation_set, citation_count, trust_level, rag_context
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def citation_node(state: InternState) -> InternState:
    """Build structured citations from reranked results.

    Reads: rerank_results, user_message
    Writes: citations, citation_set, citation_count, trust_level,
            rag_context, rag_context_tokens
    """
    t0 = time.time()
    state["current_node"] = "citation_node"

    _add_trace(state, "正在构建引用来源...")

    chunks = state.get("rerank_results", [])
    query = state.get("user_message", "")

    if not chunks:
        state["citations"] = []
        state["citation_set"] = None
        state["citation_count"] = 0
        state["trust_level"] = "unreliable"
        state["rag_context"] = ""
        state["rag_context_tokens"] = 0
        _add_trace(state, "无结果可构建引用")
        return state

    try:
        # Build citations (simplified for new implementation
        citations = []
        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            citations.append({
                "citation_id": i + 1,
                "document_name": metadata.get("file_name", "unknown"),
                "page_number": 0,
                "knowledge_base": "",
                "relevance_score": chunk.get("rerank_score", chunk.get("score", 0)),
                "full_content": chunk.get("content", ""),
            })
        
        state["citations"] = citations
        state["citation_set"] = None  # Simplified
        state["citation_count"] = len(citations)
        state["trust_level"] = "medium"

        # Build source documents summary
        state["source_documents"] = citations

        # Build RAG context (simple format)
        rag_context = _build_context(chunks)
        state["rag_context"] = rag_context
        state["rag_context_tokens"] = len(rag_context) // 2  # Rough estimate
        state["rag_context_truncated"] = len(rag_context) > 6000

        _add_trace(
            state,
            f"已构建 {len(citations)} 条引用，可信度: {state['trust_level']}"
        )

    except Exception as e:
        logger.warning(f"Citation build failed: {e}")
        # Fallback
        state["citations"] = []
        state["citation_count"] = 0
        state["trust_level"] = "unreliable"
        state["rag_context"] = _build_context(chunks)
        state["rag_context_tokens"] = 0
        _add_trace(state, "引用构建降级，使用简化格式")

    logger.info(
        f"[CitationNode] {len(chunks)} chunks → "
        f"{state['citation_count']} citations, "
        f"trust={state['trust_level']}"
    )

    return state


def _build_context(chunks: list[dict]) -> str:
    parts = ["## 知识库检索结果"]
    for i, c in enumerate(chunks):
        metadata = c.get("metadata", {})
        name = metadata.get("file_name", "unknown")
        content = c.get("content", "")
        score = c.get("rerank_score", c.get("score", 0))
        parts.append(f"\n---\n[来源{i+1}] {name} (相关度: {score:.2f})")
        parts.append(content)  # 不限制长度，完整内容都加入
    return "\n".join(parts)


def _add_trace(state: InternState, message: str):
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "citation_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
