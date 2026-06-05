"""Agent Node — Multi-step task orchestration and external tool dispatch.

Architecture:
  This node dispatches to specific agent implementations based on selected_tool.
  Currently supported: feishu_agent (chat message summary).

  For unknown tools, returns a placeholder response.

Pipeline (feishu_agent):
  1. FEISHU_QUERY     — Fetch messages from Feishu API
  2. MESSAGE_FILTER   — Score and filter important messages
  3. PROMPT_BUILD     — Build structured summary prompt
  4. LLM_GENERATION   — Call LLM to generate summary
  5. Return final_answer with structured summary
"""

import time
from datetime import datetime, timedelta

from app.graph.state import InternState
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


async def agent_node(state: InternState) -> InternState:
    """Agent dispatch node.

    Routes to specific agent implementation based on selected_tool.
    Each agent follows the same pattern:
      - Multi-phase execution with trace steps
      - Config-driven client initialization
      - Graceful degradation on error

    Currently implemented agents:
      - feishu_agent: Summarize chat messages from Feishu groups

    Args:
        state: LangGraph workflow state.

    Returns:
        Updated state with final_answer and trace_steps populated.
    """
    t_start = time.time()
    state["current_node"] = "agent_node"

    tool = state.get("selected_tool", "")
    message = state.get("user_message", "")

    state["trace_steps"] = state.get("trace_steps", []) + [{
        "node": "agent_node",
        "step_type": "agent_dispatch",
        "step_name": "Agent dispatch",
        "message": f"Dispatching agent: {tool}",
        "status": "running",
        "timestamp": _now(),
    }]

    # ---- Dispatch to specific agent ----
    if tool == "feishu_agent":
        state = await _run_feishu_agent(state)
    else:
        state = await _run_placeholder(state)

    # ---- Finalize trace ----
    duration_ms = int((time.time() - t_start) * 1000)
    state["trace_steps"][-1] = {
        "node": "agent_node",
        "step_type": "agent_dispatch",
        "step_name": "Agent dispatch",
        "message": f"Agent completed: {tool}",
        "status": "completed",
        "duration_ms": duration_ms,
        "timestamp": _now(),
    }

    return state


# ============================================================
# Feishu Agent
# ============================================================

async def _run_feishu_agent(state: InternState) -> InternState:
    """Execute Feishu chat message summary agent.

    Pipeline phases:
      FEISHU_QUERY   — Fetch messages via FeishuClient
      MESSAGE_FILTER — Score and filter important messages
      PROMPT_BUILD   — Construct structured summary prompt
      LLM_GENERATION — Generate summary via LLM

    Each phase is traced independently with duration and status.
    On failure at any phase, returns a user-friendly error message.
    """
    message = state.get("user_message", "")
    trace_steps = state.get("trace_steps", [])
    collected_slots = state.get("collected_slots", {})

    # ---- Resolve chat_id ----
    # Priority: collected_slots > message parsing
    chat_id = collected_slots.get("chat_id", "")

    # ---- Phase 1: FEISHU_QUERY ----
    t1 = time.time()
    trace_steps.append({
        "node": "agent_node",
        "step_type": "feishu_query",
        "step_name": "Feishu message fetch",
        "message": "Fetching recent messages from Feishu...",
        "status": "running",
        "timestamp": _now(),
    })

    try:
        from app.tools.feishu.feishu_client import FeishuClient

        client = FeishuClient(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            base_url=settings.feishu_base_url,
            token_cache_ttl=settings.feishu_token_cache_ttl,
            default_page_size=settings.feishu_default_page_size,
            max_retries=settings.feishu_max_retries,
            request_timeout=settings.feishu_request_timeout,
        )

        # If chat_id not specified, list chats first
        if not chat_id:
            chats_result = await client.list_chats(page_size=20)
            if not chats_result.items:
                state["final_answer"] = (
                    "No chat groups found. Please make sure the bot has been "
                    "added to at least one Feishu chat group."
                )
                state["done"] = True
                state["trace_steps"] = trace_steps
                await client.close()
                return state

            # For now, use the first chat.
            # Future: match chat name from user message using fuzzy matching.
            chat_id = chats_result.items[0].chat_id
            chat_name = chats_result.items[0].name or "Chat " + chat_id[:8]
        else:
            chat_name = "Chat " + chat_id[:8]

        # Fetch messages for the last 24 hours
        messages = await client.fetch_messages_for_summary(
            chat_id=chat_id,
            lookback_hours=24,
            max_messages=100,
        )
        total_count = len(messages)

        await client.close()

        trace_steps[-1] = {
            "node": "agent_node",
            "step_type": "feishu_query",
            "step_name": "Feishu message fetch",
            "message": f"Fetched {total_count} messages from {chat_name}",
            "status": "completed",
            "detail": {"chat_id": chat_id, "chat_name": chat_name, "total": total_count},
            "duration_ms": int((time.time() - t1) * 1000),
            "timestamp": _now(),
        }

    except ValueError as exc:
        # Config error (missing app_id/secret)
        logger.warning("Feishu config error: %s", exc)
        trace_steps[-1] = {
            "node": "agent_node",
            "step_type": "feishu_query",
            "step_name": "Feishu message fetch",
            "message": "Feishu not configured",
            "status": "failed",
            "detail": {"error": str(exc)},
            "duration_ms": int((time.time() - t1) * 1000),
            "timestamp": _now(),
        }
        state["final_answer"] = (
            "Feishu integration is not configured yet. "
            "Please set FEISHU_APP_ID and FEISHU_APP_SECRET in the environment."
        )
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    except Exception as exc:
        logger.exception("Feishu query failed")
        trace_steps[-1] = {
            "node": "agent_node",
            "step_type": "feishu_query",
            "step_name": "Feishu message fetch",
            "message": "Failed to fetch messages",
            "status": "failed",
            "detail": {"error": str(exc)},
            "duration_ms": int((time.time() - t1) * 1000),
            "timestamp": _now(),
        }
        state["final_answer"] = (
            "Failed to fetch Feishu messages. Please check that the bot "
            "has been added to the chat group and has the required permissions."
        )
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # No messages to summarize
    if total_count == 0:
        state["final_answer"] = (
            f"No messages found in chat \"{chat_name}\" in the last 24 hours. "
            "It's been quiet!"
        )
        state["done"] = True
        state["trace_steps"] = trace_steps
        return state

    # ---- Phase 2: MESSAGE_FILTER ----
    t2 = time.time()
    trace_steps.append({
        "node": "agent_node",
        "step_type": "message_filter",
        "step_name": "Message importance filter",
        "message": "Filtering important messages...",
        "status": "running",
        "timestamp": _now(),
    })

    try:
        from app.tools.feishu.feishu_message_filter import MessageFilter

        msg_filter = MessageFilter(max_results=50)
        scored = msg_filter.filter_and_score(messages)

        trace_steps[-1] = {
            "node": "agent_node",
            "step_type": "message_filter",
            "step_name": "Message importance filter",
            "message": f"Filtered {len(scored)} important messages from {total_count} total",
            "status": "completed",
            "detail": {
                "total": total_count,
                "important": len(scored),
                "categories": _count_categories(scored),
            },
            "duration_ms": int((time.time() - t2) * 1000),
            "timestamp": _now(),
        }

    except Exception as exc:
        logger.exception("Message filter failed")
        trace_steps[-1] = {
            "node": "agent_node",
            "step_type": "message_filter",
            "step_name": "Message importance filter",
            "message": "Filter failed, using all messages",
            "status": "completed",
            "detail": {"error": str(exc), "fallback": True},
            "duration_ms": int((time.time() - t2) * 1000),
            "timestamp": _now(),
        }
        # Fallback: build scored messages from raw messages
        from app.tools.feishu.feishu_message_filter import ScoredMessage
        scored = [
            ScoredMessage(
                message_id=m.message_id,
                sender_name=m.sender_name or "unknown",
                plain_text=m.plain_text,
                create_time=m.create_time,
                score=1,
                category="other",
            )
            for m in messages[:50]
        ]

    # ---- Phase 3: PROMPT_BUILD ----
    t3 = time.time()
    trace_steps.append({
        "node": "agent_node",
        "step_type": "prompt_build",
        "step_name": "Summary prompt construction",
        "message": "Building summary prompt...",
        "status": "running",
        "timestamp": _now(),
    })

    from app.tools.feishu.feishu_summary import format_messages_for_prompt
    formatted = format_messages_for_prompt(scored)
    prompt_len = len(formatted)

    trace_steps[-1] = {
        "node": "agent_node",
        "step_type": "prompt_build",
        "step_name": "Summary prompt construction",
        "message": f"Prompt built: {prompt_len} chars",
        "status": "completed",
        "detail": {"chars": prompt_len, "messages_in_prompt": len(scored)},
        "duration_ms": int((time.time() - t3) * 1000),
        "timestamp": _now(),
    }

    # ---- Phase 4: LLM_GENERATION ----
    t4 = time.time()
    trace_steps.append({
        "node": "agent_node",
        "step_type": "llm_generation",
        "step_name": "LLM summary generation",
        "message": "Generating summary with LLM...",
        "status": "running",
        "timestamp": _now(),
    })

    try:
        from app.tools.feishu.feishu_summary import (
            SUMMARY_SYSTEM_PROMPT, SUMMARY_USER_TEMPLATE,
        )

        user_prompt = SUMMARY_USER_TEMPLATE.format(
            chat_name=chat_name,
            hours=24,
            total_count=total_count,
            important_count=len(scored),
            message_list=formatted,
        )

        llm_resp = await llm_gateway.chat(
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        summary_text = llm_resp.content if hasattr(llm_resp, "content") else str(llm_resp)

        # Estimate token usage
        input_tokens = len(SUMMARY_SYSTEM_PROMPT) // 2 + len(user_prompt) // 2
        output_tokens = len(summary_text) // 2

        trace_steps[-1] = {
            "node": "agent_node",
            "step_type": "llm_generation",
            "step_name": "LLM summary generation",
            "message": "Summary generated successfully",
            "status": "completed",
            "detail": {
                "input_tokens_est": input_tokens,
                "output_tokens_est": output_tokens,
            },
            "duration_ms": int((time.time() - t4) * 1000),
            "timestamp": _now(),
        }

    except Exception as exc:
        logger.exception("LLM summarization failed")
        trace_steps[-1] = {
            "node": "agent_node",
            "step_type": "llm_generation",
            "step_name": "LLM summary generation",
            "message": "LLM failed, using fallback",
            "status": "completed",
            "detail": {"error": str(exc), "fallback": True},
            "duration_ms": int((time.time() - t4) * 1000),
            "timestamp": _now(),
        }
        # Fallback: build simple summary
        summary_text = _build_fallback_summary(scored, chat_name)

    # ---- Finalize ----
    state["final_answer"] = summary_text
    state["tokens_used"] = state.get("tokens_used", 0) + len(summary_text)
    state["done"] = True
    state["trace_steps"] = trace_steps

    logger.info(
        "FeishuAgent: chat=%s, total_msgs=%d, important=%d, summary_len=%d",
        chat_name, total_count, len(scored), len(summary_text),
    )
    return state


# ============================================================
# Placeholder (unknown agent)
# ============================================================

async def _run_placeholder(state: InternState) -> InternState:
    """Placeholder response for unrecognized agent tools."""
    message = state.get("user_message", "")
    state["final_answer"] = (
        "Your request has been received. The agent capability is under "
        "development. Currently supported: feishu message summary. "
        "Stay tuned for more capabilities!"
    )
    state["done"] = True
    logger.info("AgentNode placeholder: msg='%s...'", message[:40])
    return state


# ============================================================
# Helpers
# ============================================================

def _now() -> str:
    """UTC ISO timestamp."""
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat()


def _count_categories(scored: list) -> dict:
    """Count messages per category."""
    cats: dict = {}
    for sm in scored:
        cats[sm.category] = cats.get(sm.category, 0) + 1
    return cats


def _build_fallback_summary(scored: list, chat_name: str) -> str:
    """Build simple summary when LLM fails."""
    if not scored:
        return f"No important messages in {chat_name}."

    lines = [
        f"**Chat summary: {chat_name}**",
        f"Important messages: {len(scored)}",
        "",
    ]

    from collections import defaultdict
    by_cat = defaultdict(list)
    for sm in scored:
        by_cat[sm.category].append(sm)

    cat_labels = {
        "notification": "[Notification]",
        "risk": "[Risk/Incident]",
        "meeting": "[Meeting]",
        "task": "[Task]",
        "other": "[Other]",
    }

    for cat in ["notification", "risk", "meeting", "task", "other"]:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(cat_labels.get(cat, f"[{cat}]"))
        for sm in items[:5]:
            text = sm.plain_text[:120]
            lines.append(f"  - [{sm.time_str}] {sm.sender_name}: {text}")
        lines.append("")

    return "\n".join(lines)
