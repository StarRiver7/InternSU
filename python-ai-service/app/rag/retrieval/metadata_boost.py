"""元数据增强 — 基于元数据信号提升检索分数。

增强因子:
  1. 标题/章节块 (+0.05 每级标题匹配)
  2. 最近文档 (+0.03 对于 < 30 天的文档)
  3. 部门匹配 (+0.05 相同部门)
  4. 高块数文档 (更全面, +0.02)

所有增强是累加的，上限为 1.0。
"""

import time
from datetime import datetime, timedelta
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class MetadataBoost:
    """基于块元数据应用分数增强。"""

    def __init__(self):
        self._boost_config = {
            "title_match": 0.05,
            "recent_doc": 0.03,
            "department_match": 0.05,
            "high_quality": 0.02,
            "max_total_boost": 0.15,
        }

    def apply(
        self,
        chunks: list[dict],
        *,
        query: str = "",
        department_id: Optional[int] = None,
        recent_days: int = 30,
    ) -> list[dict]:
        """对检索结果应用元数据增强。

        参数:
            chunks: 带分数的检索结果
            query: 原始查询（用于标题匹配）
            department_id: 用户部门用于部门增强
            recent_days: 被视为"最近"的天数

        返回:
            分数增强后的块（原始分数保留为 raw_score）。
        """
        now_ms = int(time.time() * 1000)
        recent_cutoff = now_ms - (recent_days * 86400 * 1000)

        for c in chunks:
            original_score = c.get("score", 0)
            total_boost = 0.0

            # 1. Title/heading boost
            title_path = c.get("title_path", "")
            if title_path and query:
                query_terms = set(query.lower().split())
                title_terms = set(title_path.lower().split())
                if query_terms & title_terms:
                    total_boost += self._boost_config["title_match"]

            # 2. Recent document boost
            created_time = c.get("created_time", 0)
            if created_time and created_time > recent_cutoff:
                total_boost += self._boost_config["recent_doc"]

            # 3. Department match boost
            chunk_dept = c.get("department_id")
            if department_id is not None and chunk_dept == department_id:
                total_boost += self._boost_config["department_match"]

            # 4. Cap boost
            total_boost = min(total_boost, self._boost_config["max_total_boost"])

            c["raw_score"] = original_score
            c["score"] = min(1.0, original_score + total_boost)
            c["metadata_boost"] = total_boost

        # Re-sort
        chunks.sort(key=lambda x: x["score"], reverse=True)
        return chunks


metadata_boost = MetadataBoost()
