"""Advanced Duplicate Filter — semantic + structural deduplication.

Filters retrieval results to remove near-duplicate chunks
that would pollute the LLM context with redundant information.

Strategies:
  1. Exact content hash (fast)
  2. Prefix overlap (catches truncated duplicates)
  3. Semantic similarity (future: embedding cosine)
  4. Jaccard token similarity
"""

import time
import re
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class DuplicateFilter:
    """Multi-strategy duplicate chunk filter.

    Removes chunks that are substantially identical to others
    while keeping the highest-scoring version.
    """

    def __init__(
        self,
        prefix_overlap_threshold: float = 0.7,
        jaccard_threshold: float = 0.95,
    ):
        self._prefix_threshold = prefix_overlap_threshold
        self._jaccard_threshold = jaccard_threshold

    def filter(
        self,
        chunks: list[dict],
        *,
        strategy: str = "all",
    ) -> list[dict]:
        """Filter duplicate chunks.

        Args:
            chunks: retrieval results sorted by score (descending)
            strategy: "exact" | "prefix" | "jaccard" | "all"

        Returns:
            Deduplicated chunks preserving highest scores.
        """
        if not chunks or len(chunks) <= 1:
            return chunks

        start = time.time()
        original_count = len(chunks)

        result = chunks

        if strategy in ("exact", "all"):
            result = self._filter_exact(result)

        if strategy in ("prefix", "all"):
            result = self._filter_prefix_overlap(result)

        if strategy in ("jaccard", "all"):
            result = self._filter_jaccard(result)

        elapsed = int((time.time() - start) * 1000)
        removed = original_count - len(result)
        if removed > 0:
            logger.debug(
                f"[DuplicateFilter] {original_count} → {len(result)} "
                f"({removed} removed) in {elapsed}ms"
            )

        return result

    def _filter_exact(self, chunks: list[dict]) -> list[dict]:
        """Remove exact content duplicates (by MD5 hash of FULL content)."""
        import hashlib
        seen = set()
        unique = []
        for c in chunks:
            content = c.get("content", "")
            key = hashlib.md5(content.encode("utf-8")).hexdigest() if content else ""
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    def _filter_prefix_overlap(self, chunks: list[dict]) -> list[dict]:
        """Remove chunks that share a long prefix with a higher-scored chunk."""
        if len(chunks) <= 1:
            return chunks

        unique = [chunks[0]]
        for c in chunks[1:]:
            content = c.get("content", "")
            is_dup = False
            for u in unique:
                u_content = u.get("content", "")
                # Check if shorter chunk's content is a prefix of longer
                shorter = min(len(content), len(u_content))
                if shorter < 50:  # Too short to judge
                    continue
                overlap = self._prefix_match(content[:shorter], u_content[:shorter])
                if overlap >= self._prefix_threshold:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(c)
        return unique

    def _filter_jaccard(self, chunks: list[dict]) -> list[dict]:
        """Remove chunks with high Jaccard token similarity."""
        if len(chunks) <= 1:
            return chunks

        # Pre-tokenize
        tokenized = [self._tokenize(c.get("content", "")) for c in chunks]

        unique = [chunks[0]]
        unique_tokens = [tokenized[0]]

        for i in range(1, len(chunks)):
            is_dup = False
            for ut in unique_tokens:
                if self._jaccard(tokenized[i], ut) >= self._jaccard_threshold:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(chunks[i])
                unique_tokens.append(tokenized[i])
        return unique

    def get_duplicate_groups(
        self,
        chunks: list[dict],
    ) -> list[list[dict]]:
        """Group duplicates together for inspection/debugging.

        Returns list of groups, each group contains near-duplicate chunks.
        """
        if not chunks:
            return []

        groups = []
        remaining = list(chunks)

        while remaining:
            anchor = remaining.pop(0)
            group = [anchor]
            anchor_tokens = set(self._tokenize(anchor.get("content", "")))

            survivors = []
            for c in remaining:
                c_tokens = set(self._tokenize(c.get("content", "")))
                if self._jaccard(anchor_tokens, c_tokens) >= self._jaccard_threshold:
                    group.append(c)
                else:
                    survivors.append(c)
            remaining = survivors
            groups.append(group)

        return groups

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize for Jaccard comparison."""
        return re.findall(r"[\u4e00-\u9fff]+|\w+", text.lower())

    @staticmethod
    def _prefix_match(a: str, b: str) -> float:
        """Ratio of characters that match from the start."""
        if not a or not b:
            return 0.0
        min_len = min(len(a), len(b))
        matches = sum(1 for i in range(min_len) if a[i] == b[i])
        return matches / min_len

    @staticmethod
    def _jaccard(tokens_a: list[str], tokens_b: list[str]) -> float:
        """Jaccard similarity between two token sets."""
        if not tokens_a and not tokens_b:
            return 1.0
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0


duplicate_filter = DuplicateFilter()
