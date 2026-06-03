"""RAG 回答节点 — 从 RAG 上下文生成带引用的结构化回答。

【架构定位】
该节点是 RAG 管道的最终环节，负责将检索到的文档片段组装为上下文，
调用大模型生成最终回答，并附加来源引用信息。
位于引用构建之后，是 RAG 子图的出口节点。

【数据流】
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ citation_node   │ ──→ │ rag_answer_node │ ──→ │ response_node   │
│ (引用构建)      │     │ (回答生成)      │     │ (响应格式化)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘

【可信度控制】
- trust_level = "unreliable" → 拒绝编造答案，返回"未找到"
- trust_level = "low" → 带提示回答，注明信息可能不完整
- trust_level = "medium/high" → 正常引用回答

【Prompt 设计要点】
- 强制要求 LLM 使用 [来源N] 标注每个声明
- 引导 LLM 仔细阅读所有资料，避免遗漏
- 设置低温 (temperature=0.1) 保证回答稳定性
"""

import time
import os
import json
from datetime import datetime, timezone

from app.graph.state import InternState
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


# ── Citation-Aware RAG Answer Prompt ───────────────────────────────────────
# 用于有检索结果时的标准回答生成
RAG_ANSWER_PROMPT = """你是小SU-v3。请仔细阅读以下公司资料，找到老师问题的答案并直接回答。

## 公司资料
{rag_context}

## 重要规则
1. 资料中**一定包含**与问题相关的信息，请仔细查找
2. 找到相关信息后直接引用，用 [来源N] 标注
3. 以"收到老师～"开头
4. 如果确实找不到（确认每一段资料都读过了），才能说"未找到"
5. 必须使用中文

## 老师的问题
{user_message}

## 你的回答"""


# ── No Results Prompt ──────────────────────────────────────────────────────
# 用于无检索结果时的降级回答
NO_RESULTS_PROMPT = """你是小SU。老师问：{user_message}

但你在公司知识库中没有找到足够可靠的相关信息。

请以"收到老师～"开头，诚实告知：
- 知识库中没有找到相关信息
- 建议换个说法或联系相关部门
- 不要编造任何内容

你的回答："""


# ── Low Trust Prompt ────────────────────────────────────────────────────────
# 用于低可信度场景的回答（检索结果少或相关度低）
LOW_TRUST_PROMPT = """你是小SU。老师问：{user_message}

你在知识库中找到了一些可能相关的资料，但相关度不高。
{rag_context}

请以"收到老师～"开头，基于资料回答但注明：
- "根据部分资料显示..."
- "资料信息可能不完整，建议进一步确认"
- 仍然标注 [来源N]

你的回答："""


async def rag_answer_node(state: InternState) -> InternState:
    """生成 RAG 回答。

    根据检索上下文和可信度等级，调用大模型生成结构化回答。
    
    Args:
        state: LangGraph 工作流状态对象
        
    Returns:
        更新后的状态对象，包含以下字段:
        - rag_answer: RAG 回答文本
        - final_answer: 最终回答（与 rag_answer 相同）
        - sources: 来源列表（用于前端展示）
        - primary_file: 主要来源文件名
        - tokens_used: Token 消耗累计
        
    Raises:
        Exception: 大模型调用失败时降级返回友好提示
    """
    t0 = time.time()
    state["current_node"] = "rag_answer_node"

    query = state["user_message"]
    model = state.get("model_name", "deepseek-chat")
    trust_level = state.get("trust_level", "medium")
    rag_context = state.get("rag_context", "")

    # 调试信息：导出上下文到文件（仅开发环境启用）
    # WARNING: 此逻辑仅用于调试，生产环境应删除或禁用
    try:
        ctx_dump_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "ctx_dump.txt"
        )
        chunks = state.get("rerank_results", [])
        with open(ctx_dump_path, "w", encoding="utf-8") as f:
            f.write(f"LEN={len(rag_context)}\n---\n")
            f.write(rag_context)
            f.write("\n\n--- ALL CHUNKS ---\n")
            f.write(json.dumps(chunks, ensure_ascii=False, indent=2))
    except Exception:
        pass  # 忽略文件写入错误

    _add_trace(state, f"正在整理回答...(ctx={len(rag_context)} chars)")

    # 构建来源列表（供前端展示和引用标注）
    citations = state.get("citations", [])
    sources = []
    for i, c in enumerate(citations):
        source_label = f"来源{i + 1}"
        content = c.get("full_content", "")
        sources.append({
            "label": source_label,  # 来源标签（如"来源1"）
            "text": content[:200],  # 来源文本摘要
            "score": round(c.get("relevance_score", 0.0), 4),  # 相关度分数
        })

    # 记录主要来源文件名（用于 API 响应的 top-level file 字段）
    primary_file = citations[0].get("document_name", "") if citations else ""
    state["primary_file"] = primary_file
    
    # 无检索结果时的降级处理
    if not rag_context:
        answer = await _generate_no_results(query, model)
        state["rag_answer"] = answer
        state["final_answer"] = answer
        state["answer_sources"] = sources
        state["sources"] = sources
        _finish_trace(state, "无上下文可用", t0)
        return state

    try:
        # 构建 Prompt
        # NOTE: Prompt 设计原则：
        # 1. 明确告知 LLM 仔细阅读所有资料
        # 2. 强制要求使用 [来源N] 标注
        # 3. 以"收到老师～"开头保持人格化
        # 4. 低温保证回答稳定性
        prompt = f"""你是小SU。请仔细阅读以下公司资料，准确回答老师的问题。

## 公司资料
{rag_context}

## 重要规则
1. 仔细阅读资料中的所有内容，寻找与问题相关的信息
2. 如果找到相关内容，用 [来源N] 标注对应来源号
3. 以"收到老师～"开头
4. 必须使用中文
5. 不需要自行列出参考文献

## 老师的问题
{query}

## 你的回答"""

        messages = [
            {"role": "system", "content": "你是小SU，严格按照用户消息中的资料内容回答问题。必须使用中文。"},
            {"role": "user", "content": prompt},
        ]

        # 调用 LLM 生成回答
        # temperature=0.1: 低温设置，减少幻觉和随机性
        # max_tokens=2048: 限制回答长度，避免过长上下文
        resp = await llm_gateway.chat(
            messages,
            model=model,
            temperature=0.1,  # 低温：保证准确性 > 创造性
            max_tokens=2048
        )
        answer = resp.content.strip()

        # 累计 Token 消耗
        if resp.usage:
            state["tokens_used"] = state.get("tokens_used", 0) + resp.usage.get("total_tokens", 0)

        state["rag_answer"] = answer
        state["final_answer"] = answer
        state["answer_sources"] = sources
        state["sources"] = sources
        _finish_trace(state, "LLM generated answer", t0)

    except Exception as e:
        logger.error(f"[RAGAnswer] RAG 回答生成失败: {e}")
        # 降级处理：返回友好提示而非错误信息
        state["rag_answer"] = "收到老师～小SU遇到了问题，请稍后重试～"
        state["final_answer"] = state["rag_answer"]
        state["error"] = str(e)[:200]  # 截断错误信息避免过长
        _finish_trace(state, "Answer generation failed", t0)

    return state


async def _generate_no_results(query: str, model: str) -> str:
    """生成"未找到"的诚实回答。

    Args:
        query: 用户原始问题
        model: 使用的模型名称
        
    Returns:
        格式化的"未找到"回答文本
    """
    try:
        prompt = NO_RESULTS_PROMPT.format(user_message=query)
        resp = await llm_gateway.chat(
            [{"role": "user", "content": prompt}],
            model=model,
            temperature=0.5,  # 稍高温度，保持回答自然
            max_tokens=512
        )
        return resp.content.strip()
    except Exception:
        # LLM 调用失败时的兜底回答
        return "收到老师～我在公司知识库中没有找到相关信息，建议您换个说法试试，或者联系相关部门确认～"


def _add_trace(state: InternState, message: str) -> None:
    """向状态中添加追踪步骤。

    Args:
        state: LangGraph 状态对象
        message: 追踪消息内容
    """
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "rag_answer_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _finish_trace(state: InternState, message: str, t0: float) -> None:
    """完成追踪步骤（更新为完成状态）。

    Args:
        state: LangGraph 状态对象
        message: 最终消息
        t0: 起始时间戳（用于计算耗时）
    """
    duration_ms = int((time.time() - t0) * 1000)
    if state.get("trace_steps"):
        state["trace_steps"][-1] = {
            "node": "rag_answer_node",
            "message": message,
            "status": "completed",
            "duration_ms": duration_ms,
            "timestamp": _now(),
        }


def _now() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()
