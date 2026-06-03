"""元数据过滤器 — Milvus 查询的知识库权限过滤器。

构建 Milvus 过滤器表达式，用于：
  - 空间 ID 过滤（特定知识库）
  - 部门隔离（部门级可见性）
  - 可见性过滤（私有 / 部门 / 公开）
  - 创建者过滤（私有文档仅对所有者可见）
"""

from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class MetadataFilter:
    """为权限感知检索构建 Milvus 标量过滤器表达式。"""

    @staticmethod
    def build_access_filter(
        user_id: int,
        department_id: Optional[int] = None,
        allowed_space_ids: Optional[list[int]] = None,
    ) -> Optional[str]:
        """构建强制执行访问控制的 Milvus 过滤器表达式。

        规则:
          - visibility == 'public' → 始终可见
          - visibility == 'department' AND department_id 匹配 → 可见
          - creator_id == user_id → 可见（私有文档的所有者）
          - space_id in allowed_space_ids → 可见（Java 预计算）

        返回:
            Milvus 过滤器表达式字符串，如果不需要过滤器则返回 None。
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
        """过滤到特定的知识库空间。"""
        ids_str = ", ".join(str(sid) for sid in space_ids)
        return f"space_id in [{ids_str}]"

    @staticmethod
    def build_document_filter(document_ids: list[int]) -> str:
        """过滤到特定文档。
        使用 doc_id（字符串）匹配 Path A 摄入模式。
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
        """构建组合元数据过滤器。

        组合访问控制 + 空间/文档过滤器。
        当指定 document_ids 时，跳过访问控制（文档级过滤已足够）。
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
