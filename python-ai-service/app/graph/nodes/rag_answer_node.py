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
from app.prompts.internsu_prompts import SYSTEM_PROMPT
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── Citation-Aware RAG Answer Prompt ──
RAG_ANSWER_PROMPT = """你是小SU，一个刚入职的AI实习生。老师问了一个问题，请根据下面的公司资料回答。

## 公司资料（含引用来源）
{rag_context}

## 回答规则（必须严格遵守）
1. **只根据资料回答**：不要使用你自己的知识
2. **必须标注来源**：使用 [来源N] 格式标注
3. **诚实原则**：
   - 资料没有 → "老师，我在公司资料里没有找到相关信息～"
   - 资料不全 → "老师，根据现有资料，我只能确认..."
4. **引用示例**：
   - 根据《员工手册》，年假需提前3天申请[来源1]
5. **回答结构**：
   - 以"收到老师～"开头
   - 简洁回答
   - 末尾列出: 参考来源: [1]《员工手册》第5页

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
    """Generate RAG answer with trust gating.

    Reads: rag_context, citations, trust_level, user_message
    Writes: rag_answer, final_answer, answer_sources, tokens_used
    """
    t0 = time.time()
    state["current_node"] = "rag_answer_node"

    _add_trace(state, "正在整理回答...")

    query = state["user_message"]
    model = state.get("model_name", "deepseek-chat")
    trust_level = state.get("trust_level", "medium")
    rag_context = state.get("rag_context", "")

    try:
        # ── Trust Gate ──
        if trust_level == "unreliable" or not rag_context:
            answer = await _generate_no_results(query, model)
            state["rag_answer"] = answer
            state["final_answer"] = answer
            state["answer_sources"] = []
            _finish_trace(state, "知识库未找到可靠信息，已诚实告知", t0)
            logger.info(f"[RAGAnswer] No reliable results for '{query[:40]}'")
            return state

        # ── Select Prompt Based on Trust ──
        if trust_level == "low":
            prompt = LOW_TRUST_PROMPT.format(
                rag_context=rag_context,
                user_message=query,
            )
        else:
            prompt = RAG_ANSWER_PROMPT.format(
                rag_context=rag_context,
                user_message=query,
            )

        # ── Generate Answer ──
        _add_trace(state, "正在生成可信回答...")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        resp = await llm_gateway.chat(
            messages, model=model, temperature=0.5, max_tokens=2048,
        )
        answer = resp.content.strip()

        # Token accounting
        state["tokens_used"] = state.get("tokens_used", 0) + (
            resp.usage.get("total_tokens", 0) if resp.usage else 0
        )

        state["rag_answer"] = answer
        state["final_answer"] = answer

        # Collect sources used in answer
        citations = state.get("citations", [])
        state["answer_sources"] = [
            {
                "citation_id": c.get("citation_id", i + 1),
                "document_name": c.get("document_name", ""),
                "page_number": c.get("page_number", 0),
            }
            for i, c in enumerate(citations)
        ]
        state["sources"] = state["answer_sources"]

        duration_ms = int((time.time() - t0) * 1000)
        _finish_trace(state, "已基于知识库生成回答", t0)

        logger.info(
            f"[RAGAnswer] '{query[:40]}': answer_len={len(answer)}, "
            f"trust={trust_level}, {duration_ms}ms"
        )

    except Exception as e:
        logger.error(f"RAG answer generation failed: {e}")
        state["rag_answer"] = "收到老师～我刚刚整理回答时遇到一点问题，请稍后重试～"
        state["final_answer"] = state["rag_answer"]
        state["error"] = str(e)[:200]
        _finish_trace(state, "回答生成暂时不可用", t0)

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
