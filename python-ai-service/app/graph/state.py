"""LangGraph 工作流状态定义 — AI 对话系统的核心状态机。

【架构定位】
该模块定义了 InternSU AI 系统的完整状态结构，用于 LangGraph 工作流的节点间数据传递。
状态采用 TypedDict 实现，提供静态类型检查支持。

【状态分区】
- Tracing: 全链路追踪 ID
- Session: 会话基础信息
- Intent: 意图识别结果
- Clarify: 槽位收集与反问澄清
- RAG Pipeline: 知识库检索全链路
- Citation: 引用来源管理
- RAG Context: 组装后的检索上下文
- Answer: 最终回答
- Agentic: 自主检索与回退
- Graph: 工作流控制

【线程安全】
NOTE: LangGraph 状态更新非线程安全，节点内状态修改需确保原子性。
生产环境建议在状态访问处增加锁机制或使用不可变状态更新模式。
"""

from typing import TypedDict, Annotated, Optional
from operator import add


class InternState(TypedDict, total=False):
    """InternSU AI 系统 LangGraph 工作流状态定义。

    该状态定义了整个 AI 对话系统的数据流转，涵盖从意图识别到最终回答的完整链路。
    
    【状态更新约定】
    - 所有状态字段使用 Optional 类型，允许部分初始化
    - 列表类型使用 Annotated[list, add] 支持增量追加操作
    - 时间相关字段统一使用 ISO 8601 UTC 格式
    """
    
    # ==================== 全链路追踪 ====================
    trace_id: str  # 分布式追踪 ID，从 Java 端 X-Trace-Id 透传

    # ==================== 会话基础信息 ====================
    conversation_id: str  # 对话会话唯一标识（UUID）
    user_id: str          # 用户 ID（来源于 Java 端认证）
    user_message: str     # 用户原始输入消息
    conversation_context: Annotated[list[dict], add]  # 对话历史（增量追加）
    permission_context: dict  # 权限上下文（部门、角色、知识空间可见范围）

    # ==================== 意图识别 ====================
    intent: str           # 意图类型: rag | sql | chat | clarify | unknown
    intent_confidence: float  # 意图识别置信度 [0, 1]
    intent_detail: str     # 意图细分: rag_query | sql_query | chat | clarify

    # ==================== 槽位收集与反问澄清 ====================
    clarify_required: bool     # 是否需要反问澄清
    clarify_question: str      # 反问问题文本
    clarify_round: int        # 反问轮次计数（防死循环上限）
    clarify_pending: bool      # 是否处于待反问状态
    collected_slots: dict     # 已收集的槽位参数 {slot_name: value}
    clarify_slots: dict       # 待澄清的槽位定义 {slot_name: {type, question, required}}
    missing_slots: list[str]  # 缺失的必填槽位列表
    clarify_finished: bool     # 澄清流程是否完成
    pending_task: str         # 待执行的异步任务标识
    task_context: dict       # 任务上下文（用于任务恢复）

    # ==================== RAG 检索管道 ====================
    # NOTE: 以下状态贯穿整个 RAG 流程，从 Query Rewrite 到最终检索
    rag_triggered: bool       # RAG 流程是否被触发
    query_rewritten: str      # LLM 重写后的查询（语义扩展）
    retrieval_query: str      # 最终用于检索的查询文本
    space_ids: list[int]      # 允许检索的知识空间 ID 列表
    doc_ids: list[int]        # 限定检索的文档 ID 列表（可选）
    retrieval_top_k: int      # 检索阶段 Top-K 参数
    retrieval_results: list[dict]   # 原始混合检索结果
    retrieval_count: int      # 原始检索命中数量
    retrieval_elapsed_ms: int  # 检索耗时（毫秒）

    # ==================== 重排序 ====================
    rerank_results: list[dict]  # 重排序后的文档片段
    rerank_count: int         # 重排序后保留数量
    rerank_elapsed_ms: int    # 重排序耗时（毫秒）
    rerank_strategy: str      # 重排序策略: heuristic | semantic

    # ==================== 引用来源 ====================
    citations: list[dict]     # 结构化引用对象列表
    citation_set: Optional[dict]  # 完整引用集合（v2 简化版为 None）
    citation_count: int       # 引用数量
    trust_level: str          # 可信度等级: high | medium | low | unreliable
    citation_highlights: dict  # 引用高亮映射 {citation_id: [start, end]}

    # ==================== RAG 上下文 ====================
    rag_context: str         # 格式化后的 RAG 上下文（供 LLM 使用）
    rag_context_tokens: int  # 上下文 Token 估算值
    rag_context_truncated: bool  # 上下文是否被截断
    source_documents: list[dict]  # 来源文档信息（供前端展示）

    # ==================== 回答生成 ====================
    rag_answer: str          # RAG 生成的回答文本
    answer_sources: list[dict]  # 回答中实际引用的来源
    sources: list[dict]      # API 响应中的来源列表
    primary_file: str        # 主要来源文件名

    # ==================== 自主检索与回退 ====================
    retrieval_attempts: int   # 检索尝试次数（用于智能回退）
    retrieval_fallback_used: bool  # 是否使用了回退策略
    retrieval_failed: bool    # 所有检索是否全部失败

    # ==================== 工作流控制 ====================
    current_node: str        # 当前执行节点名称
    next_node: str           # 下一个待执行节点
    trace_steps: list[dict]  # 追踪步骤列表
    system_prompt: str       # 系统提示词
    final_answer: str        # 最终回答（最终输出）
    tokens_used: int         # 本次对话 Token 消耗
    model_name: str          # 使用的模型名称
    error: Optional[str]      # 错误信息（如有）
    done: bool               # 工作流是否完成


def create_initial_state(
    user_id: str,
    conversation_id: str,
    message: str,
    history: list[dict] = None,
    model_name: str = "deepseek-chat",
    restore_state: dict = None,
    doc_ids: list[int] = None,
    space_ids: list[int] = None,
    permission_context: dict = None,
    trace_id: str = "",
) -> InternState:
    """构建 LangGraph 工作流初始状态。

    创建新对话或恢复历史对话的初始状态，支持从持久化状态恢复。
    
    Args:
        user_id: 用户唯一标识（必填，来源于 Java 端 JWT 认证）
        conversation_id: 对话会话 ID（必填，用于消息持久化和上下文关联）
        message: 用户输入消息（必填）
        history: 对话历史消息列表（可选，用于上下文理解）
        model_name: 使用的 LLM 模型名称（默认 deepseek-chat）
        restore_state: 从持久化恢复的状态字典（可选）
        doc_ids: 限定检索的文档 ID 列表（可选，用于个人文档检索）
        space_ids: 允许检索的知识空间 ID 列表（必填，用于权限控制）
        permission_context: 权限上下文（可选，包含部门、角色等信息）
        trace_id: 分布式追踪 ID（可选，不填则自动生成）
        
    Returns:
        初始化后的 InternState 状态对象
        
    Note:
        - trace_id 若为空会自动从 contextvars 读取或生成 UUID
        - restore_state 用于对话恢复场景（如用户刷新页面）
        - space_ids 为空时表示用户无任何知识空间访问权限
    """
    # 参数默认值处理
    if model_name is None:
        model_name = "deepseek-chat"
    if restore_state is None:
        restore_state = {}
    rs = restore_state

    # 获取或生成追踪 ID
    if not trace_id:
        from app.core.logger import get_trace_id
        trace_id = get_trace_id()

    # 合并权限上下文（恢复状态优先于传入参数）
    pc = rs.get("permission_context", {})
    if permission_context:
        pc.update(permission_context)

    return InternState(
        # 全链路追踪
        trace_id=trace_id,

        # 会话基础信息
        conversation_id=conversation_id,
        user_id=user_id,
        user_message=message,
        conversation_context=history or [],
        permission_context=pc,

        # 意图识别（从恢复状态继承）
        doc_ids=doc_ids or rs.get("doc_ids", []),
        space_ids=space_ids or rs.get("space_ids", []),
        intent=rs.get("intent", "chat"),
        intent_confidence=rs.get("intent_confidence", 0.0),
        intent_detail=rs.get("intent_detail", "chat"),

        # 槽位收集（从恢复状态继承）
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

        # RAG 检索（初始为空，触发后填充）
        rag_triggered=False,
        query_rewritten="",
        retrieval_query="",
        retrieval_top_k=20,
        retrieval_results=[],
        retrieval_count=0,
        retrieval_elapsed_ms=0,

        # 重排序（初始为空）
        rerank_results=[],
        rerank_count=0,
        rerank_elapsed_ms=0,
        rerank_strategy="heuristic",

        # 引用来源（初始为空）
        citations=[],
        citation_set=None,
        citation_count=0,
        trust_level="medium",
        citation_highlights={},

        # RAG 上下文（初始为空）
        rag_context="",
        rag_context_tokens=0,
        rag_context_truncated=False,
        source_documents=[],

        # 回答生成（初始为空）
        rag_answer="",
        answer_sources=[],

        # 自主检索（初始状态）
        retrieval_attempts=0,
        retrieval_fallback_used=False,
        retrieval_failed=False,

        # 工作流控制
        current_node="",
        next_node="",
        trace_steps=[],
        sources=rs.get("sources", []),
        primary_file=rs.get("primary_file", ""),
        system_prompt="",
        final_answer="",
        tokens_used=0,
        model_name=model_name,
        error=None,
        done=False,
    )
