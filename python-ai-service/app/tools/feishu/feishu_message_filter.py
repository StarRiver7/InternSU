"""
FeishuMessageFilter — Enterprise message importance scoring and filtering.

Filters raw chat messages to extract important ones based on:
  - Keyword matching (notifications, releases, meetings, risks, etc.)
  - @everyone tag weighting
  - Time proximity weighting
  - Deduplication of similar messages

Used by Feishu Summary Agent to reduce noise before LLM summarization.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# Importance Keyword Configuration
# ============================================================

# High-importance keywords with their weights (used for scoring)
HIGH_IMPORTANCE_KEYWORDS: Dict[str, int] = {
    # Notifications & Announcements
    "通知": 10,
    "公告": 10,
    "重要": 8,
    "请注意": 8,
    "提醒": 7,

    # Releases & Deployments
    "上线": 9,
    "发布": 9,
    "部署": 8,
    "发版": 8,
    "灰度": 7,
    "回滚": 8,

    # Meetings
    "会议": 8,
    "开会": 8,
    "评审": 7,
    "周会": 7,
    "站会": 6,
    "复盘": 7,

    # Deadlines & Urgency
    "截止": 9,
    "紧急": 10,
    "尽快": 7,
    "DDL": 8,
    "deadline": 8,

    # Risks & Incidents
    "风险": 9,
    "故障": 10,
    "事故": 10,
    "告警": 9,
    "报警": 9,
    "Bug": 8,
    "bug": 8,
    "异常": 7,
    "报错": 8,
    "崩溃": 9,
    "宕机": 10,

    # Tasks & Requirements
    "任务": 7,
    "需求": 7,
    "排期": 7,
    "负责人": 6,
    "进度": 6,
    "TODO": 6,
    "todo": 6,
    "待办": 6,

    # Decisions & Conclusions
    "结论": 8,
    "决定": 8,
    "确认": 6,
    "方案": 6,
}

# @everyone mention weight boost
AT_EVERYONE_WEIGHT: int = 15

# Time proximity bonus:
# Messages within recent hours get bonus points (recency bias)
RECENCY_WINDOW_HOURS: int = 4
RECENCY_BONUS: int = 5

# Minimum score to be considered "important"
IMPORTANCE_THRESHOLD: int = 8

# Max important messages to return (prevents LLM token overflow)
MAX_IMPORTANT_MESSAGES: int = 50


# ============================================================
# Data Models
# ============================================================

@dataclass
class ScoredMessage:
    """A message with its importance score and metadata.

    Attributes:
        message_id: Feishu message ID.
        sender_name: Sender display name.
        plain_text: Extracted plain text content.
        create_time: Message send time.
        score: Computed importance score (higher = more important).
        matched_keywords: Keywords that matched (for debugging).
        is_at_everyone: Whether message @everyone.
        category: Detected category (notification/meeting/task/risk/other).
    """
    message_id: str
    sender_name: str
    plain_text: str
    create_time: Optional[datetime] = None
    score: int = 0
    matched_keywords: List[str] = field(default_factory=list)
    is_at_everyone: bool = False
    category: str = "other"

    @property
    def time_str(self) -> str:
        """Formatted time string for prompt display."""
        if self.create_time:
            return self.create_time.strftime("%m-%d %H:%M")
        return ""


# ============================================================
# MessageFilter
# ============================================================

class MessageFilter:
    """Enterprise message importance filter.

    Scores messages based on keyword matching, @everyone detection,
    and time proximity. Returns top-N important messages sorted by score.

    Usage:
        filt = MessageFilter()
        scored = filt.filter_and_score(messages, max_results=50)
    """

    def __init__(
        self,
        keywords: Optional[Dict[str, int]] = None,
        threshold: int = IMPORTANCE_THRESHOLD,
        max_results: int = MAX_IMPORTANT_MESSAGES,
    ):
        """Initialize filter with configurable keyword weights.

        Args:
            keywords: Keyword-to-weight mapping (defaults to built-in).
            threshold: Minimum score to be considered important.
            max_results: Maximum important messages to return.
        """
        self._keywords = keywords or HIGH_IMPORTANCE_KEYWORDS
        self._threshold = threshold
        self._max_results = max_results

        # Pre-compile keyword regex patterns for efficient matching
        # Sort by length descending to match longer keywords first
        sorted_kws = sorted(self._keywords.keys(), key=len, reverse=True)
        self._pattern = re.compile(
            "|".join(re.escape(kw) for kw in sorted_kws),
            re.IGNORECASE,
        )

    # ----------------------------------------------------------
    # Main Pipeline
    # ----------------------------------------------------------
    def filter_and_score(
        self,
        messages: List[Any],
        reference_time: Optional[datetime] = None,
        max_results: Optional[int] = None,
    ) -> List[ScoredMessage]:
        """Score and filter messages, returning top important ones.

        Pipeline:
          1. Score each message (keyword + @everyone + recency)
          2. Classify into categories
          3. Filter by threshold
          4. Sort by score descending
          5. Return top-N

        Args:
            messages: List of FeishuMessage objects.
            reference_time: Reference time for recency bonus (default now).
            max_results: Override max results limit.

        Returns:
            ScoredMessage list sorted by importance score descending.
        """
        if reference_time is None:
            reference_time = datetime.now()
        limit = max_results or self._max_results

        # Step 1: Score each message
        scored: List[ScoredMessage] = []
        for msg in messages:
            sm = self._score_one(msg, reference_time)
            if sm.score >= self._threshold:
                scored.append(sm)

        if not scored:
            logger.info("MessageFilter: no messages above threshold %d", self._threshold)
            return []

        # Step 2: Sort by score descending, then by time descending for ties
        scored.sort(
            key=lambda m: (
                -m.score,
                -(m.create_time.timestamp() if m.create_time else 0),
            )
        )

        # Step 3: Deduplicate near-duplicate messages
        # (same sender + similar content within 5 minutes → keep highest scored)
        deduped = self._deduplicate(scored)

        result = deduped[:limit]
        logger.info(
            "MessageFilter: %d messages scored, %d above threshold, %d returned",
            len(messages), len(scored), len(result),
        )
        return result

    # ----------------------------------------------------------
    # Single Message Scoring
    # ----------------------------------------------------------
    def _score_one(self, msg: Any, ref_time: datetime) -> ScoredMessage:
        """Score a single message.

        Scoring components:
          1. Keyword matching: sum of weights for matched keywords
          2. @everyone boost: AT_EVERYONE_WEIGHT if message @everyone
          3. Recency bonus: RECENCY_BONUS if within recent window
        """
        # Extract text and metadata
        plain_text = getattr(msg, "plain_text", "") or ""
        sender = getattr(msg, "sender_name", "") or "unknown"
        msg_id = getattr(msg, "message_id", "") or ""
        create_time = getattr(msg, "create_time", None)
        content = getattr(msg, "content", "") or ""

        # Component 1: Keyword matching
        # Find all unique keyword matches and sum their weights
        matched_kws: List[str] = []
        score = 0
        # Use regex finditer for efficient multi-keyword matching
        for match in self._pattern.finditer(plain_text):
            kw = match.group()
            # Normalize case for weight lookup
            kw_lower = kw.lower()
            # Try exact case, then lowercase
            weight = self._keywords.get(kw) or self._keywords.get(kw_lower)
            if weight and kw not in matched_kws:
                matched_kws.append(kw)
                score += weight

        # Also check content JSON for @everyone and keywords in card text
        if not matched_kws and content:
            for match in self._pattern.finditer(content):
                kw = match.group()
                kw_lower = kw.lower()
                weight = self._keywords.get(kw) or self._keywords.get(kw_lower)
                if weight and kw not in matched_kws:
                    matched_kws.append(kw)
                    score += weight

        # Component 2: @everyone detection
        is_at_everyone = "@everyone" in content or "@所有人" in plain_text
        if is_at_everyone:
            score += AT_EVERYONE_WEIGHT
            if "@所有人" not in matched_kws:
                matched_kws.append("@所有人")

        # Component 3: Recency bonus
        # Messages within the recent window get extra weight
        if create_time and (ref_time - create_time) < timedelta(hours=RECENCY_WINDOW_HOURS):
            score += RECENCY_BONUS

        # Determine category from matched keywords
        category = self._classify(matched_kws)

        return ScoredMessage(
            message_id=msg_id,
            sender_name=sender,
            plain_text=plain_text,
            create_time=create_time,
            score=score,
            matched_keywords=matched_kws,
            is_at_everyone=is_at_everyone,
            category=category,
        )

    # ----------------------------------------------------------
    # Category Classification
    # ----------------------------------------------------------
    @staticmethod
    def _classify(matched_keywords: List[str]) -> str:
        """Classify message into category based on matched keywords.

        Priority: risk > notification > meeting > task > other
        """
        kw_set = {k.lower() for k in matched_keywords}

        risk_kws = {"故障", "事故", "告警", "报警", "风险", "紧急", "崩溃", "宕机", "回滚"}
        notify_kws = {"通知", "公告", "重要", "请注意", "提醒", "@所有人"}
        meeting_kws = {"会议", "开会", "评审", "周会", "站会", "复盘"}
        task_kws = {"任务", "需求", "排期", "负责人", "进度", "todo", "待办", "ddl", "deadline", "截止"}
        release_kws = {"上线", "发布", "部署", "发版", "灰度"}

        if kw_set & risk_kws:
            return "risk"
        if kw_set & release_kws:
            return "notification"
        if kw_set & notify_kws:
            return "notification"
        if kw_set & meeting_kws:
            return "meeting"
        if kw_set & task_kws:
            return "task"
        return "other"

    # ----------------------------------------------------------
    # Deduplication
    # ----------------------------------------------------------
    @staticmethod
    def _deduplicate(
        scored: List[ScoredMessage],
        time_window_minutes: int = 5,
    ) -> List[ScoredMessage]:
        """Remove near-duplicate messages.

        Two messages from the same sender within time_window_minutes
        are considered duplicates; keep the one with higher score.

        This prevents the same announcement repeated by multiple people
        from dominating the summary.
        """
        if len(scored) <= 1:
            return scored

        result: List[ScoredMessage] = []
        # Track (sender, time_bucket) pairs
        seen: Dict[Tuple[str, int], ScoredMessage] = {}

        for sm in scored:
            if not sm.create_time:
                result.append(sm)
                continue

            sender = sm.sender_name or "unknown"
            # Bucket time into N-minute windows
            bucket = int(sm.create_time.timestamp() / (time_window_minutes * 60))
            key = (sender, bucket)

            if key in seen:
                # Keep the one with higher score
                if sm.score > seen[key].score:
                    # Replace: remove old, add new
                    try:
                        result.remove(seen[key])
                    except ValueError:
                        pass
                    result.append(sm)
                    seen[key] = sm
            else:
                result.append(sm)
                seen[key] = sm

        return result
