"""Cross Encoder — pairwise semantic relevance scoring.

Architecture:
  CrossEncoder(query, chunk_content) → relevance_score ∈ [0, 1]

Unlike bi-encoders (BGE-M3) that encode query and document separately,
CrossEncoder processes (query, document) as a joint input — giving
much more accurate relevance judgments at the cost of speed.

Current: heuristic-based fallback (lexical + structural signals).
Future: BGE-Reranker-v2-m3 via FlagEmbedding.
"""

import re
import time
from typing import Optional, Callable
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class CrossEncoder:
    """Pairwise relevance scorer for re-ranking.

    Processes (query, document) pairs to produce calibrated
    relevance scores that consider:
      - Exact term overlap (tf-like)
      - Positional proximity
      - Semantic signals (future: transformer-based)
    """

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or settings.bge_reranker_model
        self._model = None  # Future: FlagReranker
        self._score_fn: Optional[Callable] = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        """Load the BGE-Reranker model.

        Returns True if successfully loaded, False otherwise.
        """
        try:
            from FlagEmbedding import FlagReranker
            self._model = FlagReranker(
                self._model_name,
                use_fp16=settings.bge_use_fp16,
            )
            logger.info(f"[CrossEncoder] Loaded: {self._model_name}")
            return True
        except ImportError:
            logger.warning(
                "[CrossEncoder] FlagEmbedding not installed. "
                "Using heuristic fallback. "
                "Install with: pip install FlagEmbedding"
            )
            return False
        except Exception as e:
            logger.error(f"[CrossEncoder] Failed to load: {e}")
            return False

    def compute_scores(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        """Compute relevance scores for (query, doc) pairs.

        Args:
            query: the search query
            documents: list of document texts to score

        Returns:
            List of relevance scores in [0, 1], one per document.
        """
        if not documents:
            return []

        start = time.time()

        if self._model:
            scores = self._compute_transformer(query, documents)
        else:
            scores = self._compute_heuristic(query, documents)

        elapsed = int((time.time() - start) * 1000)
        logger.debug(
            f"[CrossEncoder] {len(documents)} pairs in {elapsed}ms "
            f"(transformer={self._model is not None})"
        )
        return scores

    def compute_score(self, query: str, document: str) -> float:
        """Compute relevance score for a single pair."""
        return self.compute_scores(query, [document])[0]

    def _compute_transformer(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        """BGE-Reranker transformer-based scoring."""
        pairs = [(query, doc) for doc in documents]
        raw_scores = self._model.compute_score(pairs)

        # Normalize to [0, 1] — BGE-Reranker scores are typically in [-10, 10]
        result = []
        if isinstance(raw_scores, (int, float)):
            raw_scores = [raw_scores]
        for s in raw_scores:
            # Sigmoid normalization
            import math
            normalized = 1.0 / (1.0 + math.exp(-float(s) / 2.0))
            result.append(round(normalized, 6))
        return result

    def _compute_heuristic(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        """Heuristic relevance scoring (lexical + structural).

        Combines:
          - TF-like term overlap (0.5 weight)
          - Term proximity / ordering (0.2 weight)
          - Content quality signals (0.3 weight)
        """
        query_lower = query.lower()
        query_terms = self._tokenize(query_lower)

        scores = []
        for doc in documents:
            doc_lower = doc.lower()
            doc_terms = self._tokenize(doc_lower)

            # 1. Term overlap (weight: 0.5)
            if not query_terms:
                overlap_score = 0.0
            else:
                matched = sum(1 for t in query_terms if t in doc_lower)
                overlap_score = matched / len(query_terms)

            # 2. Proximity: are terms close together in order? (weight: 0.2)
            proximity_score = self._proximity_score(query_terms, doc_lower)

            # 3. Quality signals (weight: 0.3)
            quality_score = self._quality_score(doc)

            # Combined: 0.5×overlap + 0.2×proximity + 0.3×quality
            combined = (
                0.5 * overlap_score +
                0.2 * proximity_score +
                0.3 * quality_score
            )

            scores.append(round(min(1.0, max(0.0, combined)), 6))

        return scores

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Extract meaningful tokens from text.
        
        For Chinese: character bigrams for better recall (single chars are too granular).
        For English: word-level tokens.
        """
        text_lower = text.lower()
        # Split into Chinese and non-Chinese segments
        segments = re.split(r'([\u4e00-\u9fff]+)', text_lower)
        tokens = []
        for seg in segments:
            if not seg:
                continue
            if re.match(r'[\u4e00-\u9fff]', seg):
                # Chinese: character bigrams + single chars for short queries
                if len(seg) <= 3:
                    tokens.extend(list(seg))  # Single chars for short queries
                else:
                    tokens.extend(list(seg))  # Single chars
                    tokens.extend(seg[i:i+2] for i in range(len(seg)-1))  # Bigrams
            else:
                tokens.extend(re.findall(r'\w+', seg))
        return tokens

    @staticmethod
    def _proximity_score(query_terms: list[str], doc: str) -> float:
        """How well do query terms appear in order and proximity?"""
        if not query_terms:
            return 0.0

        doc_lower = doc.lower()
        positions = []
        for term in query_terms:
            pos = doc_lower.find(term)
            positions.append(pos if pos >= 0 else -1)

        if len(positions) <= 1:
            # Single term: check presence with positional bonus
            return 0.5 if (positions and positions[0] >= 0) else 0.0

        # Count consecutive increasing matches
        consecutive = 0
        valid_positions = [p for p in positions if p >= 0]
        for i in range(len(valid_positions) - 1):
            if valid_positions[i + 1] > valid_positions[i]:
                consecutive += 1

        total_pairs = len(positions) - 1
        return consecutive / total_pairs if total_pairs > 0 else 0.0

    @staticmethod
    def _quality_score(doc: str) -> float:
        """Content quality heuristics."""
        score = 0.5  # Baseline

        # Penalize very short docs
        if len(doc) < 50:
            score -= 0.3
        # Penalize very long docs
        elif len(doc) > 3000:
            score -= 0.1
        # Reward moderate length
        elif 200 < len(doc) < 1500:
            score += 0.2

        # Reward structured content (headings, lists)
        if re.search(r"(第[一二三四五六七八九十\d]+[章节]|\d+\.\s|[-•·]\s)", doc):
            score += 0.15

        # Penalize excessive whitespace
        whitespace_ratio = doc.count(" ") / max(len(doc), 1)
        if whitespace_ratio > 0.3:
            score -= 0.1

        return min(1.0, max(0.0, score))


cross_encoder = CrossEncoder()
