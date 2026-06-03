"""引用构建节点 — RAG 管道中的引用来源组装与可信度评估。

【架构定位】
该节点位于 RAG 工作流的重排序阶段之后、回答生成阶段之前，核心职责是：
1. 从重排序后的文档片段中提取结构化引用元数据
2. 评估引用集合的整体可信度等级
3. 组装格式化为大模型友好的 RAG 上下文字符串

【数据流】
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ rerank_results  │ ──→ │ citation_node   │ ──→ │ rag_answer_node │
│ (重排序结果)     │      │ (引用构建)       │     │ (回答生成)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘

【状态读写】
- 读取: rerank_results, user_message
- 写入: citations, citation_set, citation_count, trust_level,
        rag_context, rag_context_tokens, rag_context_truncated

【设计要点】
- 引用 ID 采用自增序号，便于前端定位高亮
- 可信度分级: unreliable(不可靠) / low(低) / medium(中) / high(高)
- 上下文格式遵循"## 标题 + --- 分隔 + [来源N] 文件名 (相关度) + 内容"的结构
"""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from app.graph.state import InternState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def citation_node(state: InternState) -> InternState:
    """构建结构化引用并组装 RAG 上下文。

    将重排序后的文档片段转换为标准引用格式，并评估可信度等级。
    
    Args:
        state: LangGraph 工作流状态对象，包含上游节点的输出数据
        
    Returns:
        更新后的状态对象，包含以下新增字段:
        - citations: 结构化引用列表
        - citation_set: 引用集合对象（当前版本简化为 None）
        - citation_count: 引用数量
        - trust_level: 可信度等级 (unreliable/low/medium/high)
        - rag_context: 组装后的 RAG 上下文字符串
        - rag_context_tokens: 上下文 Token 估算值
        - rag_context_truncated: 是否被截断
        
    Raises:
        Exception: 引用构建失败时会被捕获并降级处理，不会向上抛出
    """
    t0 = time.time()
    state["current_node"] = "citation_node"

    _add_trace(state, "正在构建引用来源...")

    chunks = state.get("rerank_results", [])
    query = state.get("user_message", "")

    # 边界情况处理：无检索结果时直接返回空引用
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
        # 构建结构化引用列表
        # NOTE: 引用 ID 从 1 开始而非 0，便于前端展示时更符合用户习惯
        citations = []
        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            citations.append({
                "citation_id": i + 1,  # 引用唯一标识（自增）
                "document_name": metadata.get("file_name", "unknown"),  # 来源文件名
                "page_number": metadata.get("page_number", 0),  # 页码（PDF/DOCX）
                "knowledge_base": metadata.get("space_name", ""),  # 所属知识空间
                "relevance_score": chunk.get("rerank_score", chunk.get("score", 0)),  # 相关度分数
                "full_content": chunk.get("content", ""),  # 完整内容（用于高亮定位）
            })
        
        state["citations"] = citations
        state["citation_set"] = None  # v2 简化实现，完整版会使用 CitationSet 对象
        state["citation_count"] = len(citations)
        
        # 可信度评估：根据引用数量和相关度综合判断
        # WARNING: 当前为简化逻辑，生产环境应考虑更多因素（如来源多样性、时间新鲜度等）
        if len(citations) >= 3 and any(c.get("relevance_score", 0) > 0.7 for c in citations):
            state["trust_level"] = "high"
        elif len(citations) >= 1:
            state["trust_level"] = "medium"
        else:
            state["trust_level"] = "low"

        # 保存来源文档摘要供前端展示
        state["source_documents"] = citations

        # 组装 RAG 上下文：格式化为大模型可直接理解的结构化文本
        # NOTE: 不限制内容长度，确保大模型获得完整上下文（截断由下游节点处理）
        rag_context = _build_context(chunks)
        state["rag_context"] = rag_context
        # 粗略估算：1 Token ≈ 2 字符（中文场景略偏多但足够保守）
        state["rag_context_tokens"] = len(rag_context) // 2
        state["rag_context_truncated"] = len(rag_context) > 6000  # 标记是否可能需要截断

        _add_trace(
            state,
            f"已构建 {len(citations)} 条引用，可信度: {state['trust_level']}"
        )

    except Exception as e:
        logger.warning(f"[CitationNode] 引用构建失败: {e}")
        # 降级处理：即使构建失败也要保证流程能继续
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


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    """组装 RAG 上下文字符串。

    将多个文档片段格式化为大模型友好的结构化格式，包含来源标识和相关度信息。
    
    Args:
        chunks: 重排序后的文档片段列表，每个片段包含 content、metadata、score 等字段
        
    Returns:
        格式化后的上下文字符串，结构如下:
        ## 知识库检索结果
        ---
        [来源1] 文件名 (相关度: 0.85)
        内容文本...
        ---
        [来源2] 文件名 (相关度: 0.72)
        内容文本...
    """
    parts = ["## 知识库检索结果"]
    for i, c in enumerate(chunks):
        metadata = c.get("metadata", {})
        name = metadata.get("file_name", "unknown")
        content = c.get("content", "")
        score = c.get("rerank_score", c.get("score", 0))
        parts.append(f"\n---\n[来源{i+1}] {name} (相关度: {score:.2f})")
        parts.append(content)  # 不限制长度，完整内容都加入（下游节点负责截断）
    return "\n".join(parts)


def _add_trace(state: InternState, message: str) -> None:
    """向状态中添加追踪步骤。

    用于记录节点执行过程，支持前端实时展示工作进度。
    
    Args:
        state: LangGraph 状态对象
        message: 追踪消息内容
    """
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "citation_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _now() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串。
    
    Returns:
        ISO 8601 格式的 UTC 时间戳
    """
    return datetime.now(timezone.utc).isoformat()
