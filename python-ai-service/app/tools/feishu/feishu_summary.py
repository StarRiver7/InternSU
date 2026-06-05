"""
FeishuSummary — Prompt builder and LLM summarizer for chat messages.

Converts scored messages into a structured summary prompt,
calls LLM to extract key information, and returns formatted result.

Output format:
  [Notification] ...
  [Task] ...
  [Meeting] ...
  [Risk] ...
  [Other] ...
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.tools.feishu.feishu_message_filter import ScoredMessage

logger = logging.getLogger(__name__)


# ============================================================
# Summary System Prompt
# ============================================================

SUMMARY_SYSTEM_PROMPT = """You are a senior enterprise assistant AI. Your task is to read enterprise chat messages and produce a structured summary.

## Summary Rules

1. Extract and categorize information into sections:
   - [Notification]: Official announcements, release notices, policy changes
   - [Task]: Assigned tasks, action items, TODO items, deadlines
   - [Meeting]: Meeting announcements, review schedules, meeting conclusions
   - [Risk]: Incidents, bugs, alerts, urgent issues, production problems
   - [Other]: Important discussions that don't fit above categories

2. For each item, include:
   - Who (sender name if available)
   - What (core content in 1-2 lines)
   - When (time or deadline)

3. Quality requirements:
   - Do NOT simply repeat the chat messages verbatim
   - Prioritize decisions, conclusions, and action items over chatter
   - If a topic spans multiple messages, merge them into one entry
   - Omit trivial conversations (greetings, emojis, off-topic chat)
   - Use professional but friendly tone

4. Output format:
   Start each section with its marker, followed by bullet points (- ).
   If a section has no relevant content, output "None" under it.
   Keep the total summary concise, under 500 words."""


SUMMARY_USER_TEMPLATE = """Below are recent important messages from the enterprise chat group.

Chat name: {chat_name}
Time range: last {hours}h
Total messages: {total_count}
Important messages (filtered): {important_count}

---
{message_list}
---

Please produce a structured summary following the format rules."""


# ============================================================
# Message Formatter for Prompt
# ============================================================

def format_messages_for_prompt(
    messages: List[ScoredMessage],
    max_chars_per_msg: int = 300,
) -> str:
    """Format scored messages into a compact prompt string.

    Each message is formatted as:
      [time] sender (score:N, cat:category):
        text...

    Messages are grouped by category for easier LLM processing.

    Args:
        messages: Scored messages sorted by importance.
        max_chars_per_msg: Max characters per message text (truncation).

    Returns:
        Formatted string ready for prompt insertion.
    """
    if not messages:
        return "(No important messages found)"

    lines: List[str] = []
    current_category = ""

    for sm in messages:
        # Add category header when switching categories
        cat_label = _category_label(sm.category)
        if sm.category != current_category:
            current_category = sm.category
            lines.append(f"\n--- {cat_label} ---")

        # Truncate long messages
        text = sm.plain_text
        if len(text) > max_chars_per_msg:
            text = text[:max_chars_per_msg - 3] + "..."

        # Format: [HH:MM] Name: text
        time_str = sm.time_str or "--:--"
        at_flag = " [@all]" if sm.is_at_everyone else ""
        lines.append(f"[{time_str}] {sm.sender_name}{at_flag}: {text}")

    return "\n".join(lines)


def _category_label(category: str) -> str:
    """Chinese category label for prompt display."""
    labels = {
        "notification": "Notification/Announcement",
        "meeting": "Meeting",
        "task": "Task/To-do",
        "risk": "Risk/Incident",
        "other": "Other Important",
    }
    return labels.get(category, category)


# ============================================================
# Summary Generator
# ============================================================

class FeishuSummaryGenerator:
    """Generates structured summary from scored messages using LLM.

    Usage:
        gen = FeishuSummaryGenerator(llm_chat_fn)
        summary = await gen.generate(messages, chat_name="Tech Team")
    """

    def __init__(self, llm_chat_fn):
        """Initialize with an async LLM chat function.

        Args:
            llm_chat_fn: Async function with signature:
                async def fn(messages, temperature, max_tokens) -> LLMResponse
                where LLMResponse has .content (str).
        """
        self._chat = llm_chat_fn

    async def generate(
        self,
        messages: List[ScoredMessage],
        chat_name: str = "",
        hours_back: int = 24,
        total_count: int = 0,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> Dict[str, Any]:
        """Generate structured summary from scored messages.

        Pipeline:
          1. Format messages into prompt string (grouped by category)
          2. Build system + user messages
          3. Call LLM
          4. Parse output into structured sections (fallback if parsing fails)

        Args:
            messages: Scored messages sorted by importance.
            chat_name: Chat group name for context.
            hours_back: Time window for display.
            total_count: Total raw message count (before filtering).
            temperature: LLM temperature (lower = more focused).
            max_tokens: Max output tokens.

        Returns:
            Dict with keys: summary (str), sections (dict), stats (dict).
        """
        # Step 1: Format messages for prompt
        formatted = format_messages_for_prompt(messages)

        # Step 2: Build prompts
        user_prompt = SUMMARY_USER_TEMPLATE.format(
            chat_name=chat_name or "company chat",
            hours=hours_back,
            total_count=total_count,
            important_count=len(messages),
            message_list=formatted,
        )

        llm_messages = [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Step 3: Call LLM
        try:
            resp = await self._chat(
                messages=llm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            summary_text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:
            logger.exception("LLM summarization failed")
            # Fallback: build simple summary from scored messages
            summary_text = _build_fallback_summary(messages, chat_name, hours_back)
            return {
                "summary": summary_text,
                "sections": {},
                "stats": {
                    "total_messages": total_count,
                    "important_messages": len(messages),
                    "fallback": True,
                    "error": str(exc),
                },
            }

        # Step 4: Parse sections from LLM output
        sections = _parse_sections(summary_text)

        # Step 5: Build stats
        stats = _build_stats(messages, total_count, hours_back)

        return {
            "summary": summary_text,
            "sections": sections,
            "stats": stats,
        }


# ============================================================
# Output Parsing
# ============================================================

def _parse_sections(summary_text: str) -> Dict[str, str]:
    """Parse LLM output into structured sections.

    Splits on section markers like [Notification], [Task], etc.
    If parsing fails, returns entire text under "raw" key.

    Args:
        summary_text: Raw LLM output.

    Returns:
        Dict mapping section name to content string.
    """
    import re

    sections: Dict[str, str] = {}
    # Known section markers
    markers = [
        ("notification", r"\[Notification\]"),
        ("task", r"\[Task\]"),
        ("meeting", r"\[Meeting\]"),
        ("risk", r"\[Risk\]"),
        ("other", r"\[Other\]"),
    ]

    remaining = summary_text
    for i, (key, pattern) in enumerate(markers):
        match = re.search(pattern, remaining, re.IGNORECASE)
        if not match:
            sections[key] = ""
            continue

        start = match.end()
        # Find next marker or end of text
        next_start = len(remaining)
        for _, next_pattern in markers[i + 1:]:
            next_match = re.search(next_pattern, remaining[start:], re.IGNORECASE)
            if next_match:
                next_start = start + next_match.start()
                break

        content = remaining[start:next_start].strip()
        # Clean up: remove leading/trailing whitespace and bullets
        sections[key] = content
        remaining = remaining[next_start:]

    # If no sections were parsed, put everything under "raw"
    if not any(sections.values()):
        sections["raw"] = summary_text

    return sections


def _build_stats(
    messages: List[ScoredMessage],
    total_count: int,
    hours_back: int,
) -> Dict[str, Any]:
    """Build summary statistics from scored messages.

    Includes: message counts by category, time range, top keywords.
    """
    categories: Dict[str, int] = {}
    senders: Dict[str, int] = {}
    top_kws: Dict[str, int] = {}

    for sm in messages:
        categories[sm.category] = categories.get(sm.category, 0) + 1
        if sm.sender_name:
            senders[sm.sender_name] = senders.get(sm.sender_name, 0) + 1
        for kw in sm.matched_keywords:
            top_kws[kw] = top_kws.get(kw, 0) + 1

    # Sort and limit top keywords
    sorted_kws = sorted(top_kws.items(), key=lambda x: -x[1])[:10]

    # Time range
    times = [sm.create_time for sm in messages if sm.create_time]
    time_range = ""
    if times:
        t_min = min(times)
        t_max = max(times)
        time_range = f"{t_min.strftime('%m-%d %H:%M')} ~ {t_max.strftime('%H:%M')}"

    return {
        "total_messages": total_count,
        "important_messages": len(messages),
        "hours_back": hours_back,
        "categories": categories,
        "active_senders": len(senders),
        "top_senders": sorted(senders.items(), key=lambda x: -x[1])[:5],
        "top_keywords": sorted_kws,
        "time_range": time_range,
    }


def _build_fallback_summary(
    messages: List[ScoredMessage],
    chat_name: str,
    hours_back: int,
) -> str:
    """Build a simple summary when LLM is unavailable.

    Groups messages by category and lists top items.
    This is a degradation strategy, not the primary path.
    """
    if not messages:
        return f"No important messages found in the last {hours_back} hours."

    lines = [
        f"Chat: {chat_name or 'company chat'}",
        f"Time: last {hours_back}h, {len(messages)} important messages",
        "",
    ]

    # Group by category
    from collections import defaultdict
    by_cat: Dict[str, List[ScoredMessage]] = defaultdict(list)
    for sm in messages:
        by_cat[sm.category].append(sm)

    cat_order = ["notification", "risk", "meeting", "task", "other"]
    cat_labels = {
        "notification": "[Notification]",
        "risk": "[Risk/Incident]",
        "meeting": "[Meeting]",
        "task": "[Task]",
        "other": "[Other]",
    }

    for cat in cat_order:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(cat_labels.get(cat, f"[{cat}]"))
        for sm in items[:5]:
            text = sm.plain_text[:120]
            lines.append(f"  - [{sm.time_str}] {sm.sender_name}: {text}")
        lines.append("")

    return "\n".join(lines)
