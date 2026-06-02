"""Metadata Filter — knowledge base permission filter for Milvus queries.

Builds Milvus filter expressions for:
  - Space ID filtering (specific knowledge bases)
  - Department isolation (department-scoped visibility)
  - Visibility filtering (private / department / public)
  - Creator filtering (private docs only visible to owner)
"""

from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class MetadataFilter:
    """Build Milvus scalar filter expressions for permission-aware retrieval."""

    @staticmethod
    def build_access_filter(
        user_id: int,
        department_id: Optional[int] = None,
        allowed_space_ids: Optional[list[int]] = None,
    ) -> Optional[str]:
        """Build a Milvus filter expression that enforces access control.

        Rules:
          - visibility == 'public' → always visible
          - visibility == 'department' AND department_id match → visible
          - creator_id == user_id → visible (owner of private docs)
          - space_id in allowed_space_ids → visible (Java pre-computed)

        Returns:
            Milvus filter expression string, or None if no filter needed.
        """
        conditions = []

        # Public docs
        conditions.append('visibility == "public"')

        # Department docs
        if department_id is not None:
            conditions.append(
                f'(visibility == "department" and department_id == {department_id})'
            )

        # Owner's private docs
        conditions.append(f"(creator_id == {user_id})")

        # Pre-computed allowed spaces (from Java service)
        if allowed_space_ids:
            ids_str = ", ".join(str(sid) for sid in allowed_space_ids)
            conditions.append(f"(space_id in [{ids_str}])")

        return " or ".join(f"({c})" for c in conditions)

    @staticmethod
    def build_space_filter(space_ids: list[int]) -> str:
        """Filter to specific knowledge spaces."""
        ids_str = ", ".join(str(sid) for sid in space_ids)
        return f"space_id in [{ids_str}]"

    @staticmethod
    def build_document_filter(document_ids: list[int]) -> str:
        """Filter to specific documents.
        Uses doc_id (string) to match Path A ingestion schema.
        """
        ids_str = ", ".join(f'"{did}"' for did in document_ids)
        return f"doc_id in [{ids_str}]"

    @staticmethod
    def build_combined_filter(
        user_id: int,
        department_id: Optional[int] = None,
        space_ids: Optional[list[int]] = None,
        document_ids: Optional[list[int]] = None,
    ) -> Optional[str]:
        """Build a combined metadata filter.

        Combines access control + space/doc filters.
        When document_ids is specified, skip access control (doc-level filtering suffices).
        """
        parts = []

        # Document filter (uses doc_id string field from Path A schema)
        if document_ids:
            parts.append(MetadataFilter.build_document_filter(document_ids))
        else:
            # Access control (only when no specific documents requested)
            access = MetadataFilter.build_access_filter(
                user_id, department_id, space_ids
            )
            if access:
                parts.append(access)

        if not parts:
            return None

        return " and ".join(f"({p})" for p in parts)


metadata_filter = MetadataFilter()
