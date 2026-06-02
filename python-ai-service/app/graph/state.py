from typing import TypedDict, Annotated, Optional
from operator import add


class InternState(TypedDict, total=False):
    # -- Tracing --
    trace_id: str                     # distributed trace ID from Java X-Trace-Id

    # -- Session --
    conversation_id: str
    user_id: str
    user_message: str
    conversation_context: Annotated[list[dict], add]
    permission_context: dict

    # -- Intent --
    intent: str
    intent_confidence: float
    intent_detail: str               # "rag_query" | "sql_query" | "chat" | "clarify"

    # -- Clarify --
    clarify_required: bool
    clarify_question: str
    clarify_round: int
    clarify_pending: bool
    collected_slots: dict
    clarify_slots: dict
    missing_slots: list[str]
    clarify_finished: bool
    pending_task: str
    task_context: dict

    # -- RAG Pipeline --
    rag_triggered: bool              # Whether RAG was activated
    query_rewritten: str             # LLM-rewritten query
    retrieval_query: str             # Actual query used for retrieval
    space_ids: list[int]             # Allowed knowledge bases
    doc_ids: list[int]               # Specific document IDs to filter by
    retrieval_top_k: int             # Top-K for retrieval
    retrieval_results: list[dict]    # Raw hybrid retrieval results
    retrieval_count: int             # Number of raw hits
    retrieval_elapsed_ms: int        # Retrieval timing

    # -- Rerank --
    rerank_results: list[dict]       # Re-ranked chunks
    rerank_count: int                # Post-rerank count
    rerank_elapsed_ms: int           # Rerank timing
    rerank_strategy: str             # "heuristic" | "semantic"

    # -- Citation --
    citations: list[dict]            # Structured citation objects
    citation_set: Optional[dict]     # Full CitationSet dict
    citation_count: int              # Number of citations
    trust_level: str                 # "high" | "medium" | "low" | "unreliable"
    citation_highlights: dict        # Source highlight map

    # -- RAG Context --
    rag_context: str                 # Formatted context for LLM
    rag_context_tokens: int          # Estimated token count
    rag_context_truncated: bool      # Whether context was truncated
    source_documents: list[dict]     # Source document info

    # -- Answer --
    rag_answer: str                  # Final RAG answer
    answer_sources: list[dict]       # Sources used in answer
    sources: list[dict]              # Sources output (for API response)

    # -- Agentic Retrieval --
    retrieval_attempts: int          # Number of retrieval attempts
    retrieval_fallback_used: bool    # Whether fallback was triggered
    retrieval_failed: bool           # Whether all retrieval failed

    # -- Graph --
    current_node: str
    next_node: str
    trace_steps: list[dict]
    system_prompt: str
    final_answer: str
    tokens_used: int
    model_name: str
    error: Optional[str]
    done: bool


def create_initial_state(
    user_id: str,
    conversation_id: str,
    message: str,
    history: list[dict] = None,
    model_name: str = "deepseek-chat",
    restore_state: dict = None,
    doc_ids: list[int] = None,
    trace_id: str = "",
) -> InternState:
    """Construct LangGraph initial state.

    Args:
        trace_id: distributed trace ID, read from contextvars by caller.
        doc_ids: specific document IDs to restrict RAG retrieval scope.
    """
    if model_name is None:
        model_name = "deepseek-chat"
    if restore_state is None:
        restore_state = {}
    rs = restore_state

    if not trace_id:
        from app.core.logger import get_trace_id
        trace_id = get_trace_id()

    return InternState(
        trace_id=trace_id,

        conversation_id=conversation_id,
        user_id=user_id,
        user_message=message,
        conversation_context=history or [],
        permission_context=rs.get("permission_context", {}),

        doc_ids=doc_ids or rs.get("doc_ids", []),
        intent=rs.get("intent", "chat"),
        intent_confidence=rs.get("intent_confidence", 0.0),
        intent_detail=rs.get("intent_detail", "chat"),

        clarify_required=rs.get("clarify_required", False),
        clarify_question=rs.get("clarify_question", ""),
        clarify_round=rs.get("clarify_round", 0),
        clarify_pending=rs.get("clarify_pending", False),
        collected_slots=rs.get("collected_slots", {}),
        clarify_slots=rs.get("clarify_slots", {}),
        missing_slots=rs.get("missing_slots", []),
        clarify_finished=rs.get("clarify_finished", False),
        pending_task=rs.get("pending_task", ""),
        task_context=rs.get("task_context", {}),

        rag_triggered=False,
        query_rewritten="",
        retrieval_query="",
        space_ids=rs.get("space_ids", []),
        retrieval_top_k=20,
        retrieval_results=[],
        retrieval_count=0,
        retrieval_elapsed_ms=0,

        rerank_results=[],
        rerank_count=0,
        rerank_elapsed_ms=0,
        rerank_strategy="heuristic",

        citations=[],
        citation_set=None,
        citation_count=0,
        trust_level="medium",
        citation_highlights={},

        rag_context="",
        rag_context_tokens=0,
        rag_context_truncated=False,
        source_documents=[],

        rag_answer="",
        answer_sources=[],

        retrieval_attempts=0,
        retrieval_fallback_used=False,
        retrieval_failed=False,

        current_node="",
        next_node="",
        trace_steps=[],
        sources=rs.get("sources", []),
        system_prompt="",
        final_answer="",
        tokens_used=0,
        model_name=model_name,
        error=None,
        done=False,
    )