"""RAG Answer Node — generate citation-aware answer from RAG context.

Reads: rag_context, citations, trust_level, user_message
Writes: rag_answer, final_answer, answer_sources, tokens_used

Trust gating:
  - trust_level = "unreliable" → refuse to fabricate
  - trust_level = "low" → answer with caveat
  - trust_level = "medium"/"high" → normal answer

Citation-aware prompt enforces:
  ○ Only answer from provided context
  ○ Every claim must cite [来源N]
  ○ If context lacks info, say so honestly
"""

import time
from datetime import datetime, timezone

from app.graph.state import InternState
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── Citation-Aware RAG Answer Prompt ──
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

# ── No Results Prompt ──
NO_RESULTS_PROMPT = """你是小SU。老师问：{user_message}

但你在公司知识库中没有找到足够可靠的相关信息。

请以"收到老师～"开头，诚实告知：
- 知识库中没有找到相关信息
- 建议换个说法或联系相关部门
- 不要编造任何内容

你的回答："""

# ── Low Trust Prompt ──
LOW_TRUST_PROMPT = """你是小SU。老师问：{user_message}

你在知识库中找到了一些可能相关的资料，但相关度不高。
{rag_context}

请以"收到老师～"开头，基于资料回答但注明：
- "根据部分资料显示..."
- "资料信息可能不完整，建议进一步确认"
- 仍然标注 [来源N]

你的回答："""


async def rag_answer_node(state: InternState) -> InternState:
    """Generate RAG answer."""
    t0 = time.time()
    state["current_node"] = "rag_answer_node"

    query = state["user_message"]
    model = state.get("model_name", "deepseek-chat")
    trust_level = state.get("trust_level", "medium")
    rag_context = state.get("rag_context", "")

    # Dump context to file for debugging
    try:
        import os as _os2
        import json
        chunks = state.get("rerank_results", [])
        _dump = _os2.path.join(_os2.path.dirname(_os2.path.dirname(_os2.path.dirname(_os2.path.abspath(__file__)))), "ctx_dump.txt")
        with open(_dump, "w", encoding="utf-8") as _f2:
            _f2.write(f"LEN={len(rag_context)}\n---\n")
            _f2.write(rag_context)
            _f2.write("\n\n--- ALL CHUNKS ---\n")
            _f2.write(json.dumps(chunks, ensure_ascii=False, indent=2))
    except Exception as e:
        pass
    _add_trace(state, f"正在整理回答...(ctx={len(rag_context)} chars)")

    citations = state.get("citations", [])
    sources = []
    for i, c in enumerate(citations):
        source_label = f"来源{i + 1}"
        content = c.get("full_content", "")
        sources.append({
            source_label: content[:200],
            "score": round(c.get("relevance_score", 0.0), 4),
        })

    # Primary file (document name of the top result)
    primary_file = citations[0].get("document_name", "") if citations else ""
    state["primary_file"] = primary_file
    
    if not rag_context:
        answer = await _generate_no_results(query, model)
        state["rag_answer"] = answer
        state["final_answer"] = answer
        state["answer_sources"] = sources
        state["sources"] = sources
        _finish_trace(state, "无上下文可用", t0)
        return state

    try:
        # Build the final answer with sources
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

        resp = await llm_gateway.chat(messages, model=model, temperature=0.1, max_tokens=2048)
        answer = resp.content.strip()

        state["tokens_used"] = state.get("tokens_used", 0) + (resp.usage.get("total_tokens", 0) if resp.usage else 0)
        state["rag_answer"] = answer
        state["final_answer"] = answer
        state["answer_sources"] = sources
        state["sources"] = sources
        _finish_trace(state, "LLM generated answer", t0)

    except Exception as e:
        logger.error(f"RAG answer failed: {e}")
        state["rag_answer"] = "收到老师～小SU遇到了问题，请稍后重试～"
        state["final_answer"] = state["rag_answer"]
        state["error"] = str(e)[:200]
        _finish_trace(state, "Answer generation failed", t0)

    return state


async def _generate_no_results(query: str, model: str) -> str:
    """Generate honest no-results response."""
    try:
        prompt = NO_RESULTS_PROMPT.format(user_message=query)
        resp = await llm_gateway.chat(
            [{"role": "user", "content": prompt}],
            model=model, temperature=0.5, max_tokens=512,
        )
        return resp.content.strip()
    except Exception:
        return "收到老师～我在公司知识库中没有找到相关信息，建议您换个说法试试，或者联系相关部门确认～"


def _add_trace(state: InternState, message: str):
    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "rag_answer_node",
        "message": message,
        "status": "running",
        "timestamp": _now(),
    }]


def _finish_trace(state: InternState, message: str, t0: float):
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
    return datetime.now(timezone.utc).isoformat()
