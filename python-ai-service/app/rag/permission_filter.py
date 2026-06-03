
"""RAG 权限过滤器。

根据知识空间的 visibility 实现三层权限过滤:
  - private:  仅创建者可见
  - department: 同部门成员可见
  - public:   全员可见
"""

from app.core.logger import get_logger

logger = get_logger(__name__)


class PermissionFilter:
    """RAG 检索结果权限过滤器。

    在 Milvus 检索后、注入 Prompt 前执行过滤。
    过滤规则来自 Java 端传入的 permission_context。
    """

    def filter_chunks(
        self,
        chunks: list[dict],
        user_id: str,
        department_id: int,
        department_path: str,
        allowed_space_ids: list[int],
    ) -> list[dict]:
        """过滤 chunks，仅保留用户有权访问的。

        Args:
            chunks: Milvus 返回的 chunk 列表，每个含 metadata
            user_id: 当前用户 ID
            department_id: 当前用户部门 ID
            department_path: 当前用户部门路径 (如 /1/3)
            allowed_space_ids: Java 端预计算的可访问 space ID

        Returns:
            过滤后的 chunks
        """
        if allowed_space_ids is None:
            # 无权限上下文（未传入），返回全部（兼容模式）
            logger.warning("[PermissionFilter] 未提供权限上下文，返回全部 chunk")
            return chunks

        filtered = []
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            space_id = meta.get("space_id", 0)
            visibility = meta.get("visibility", "public")
            creator_id = str(meta.get("creator_id", ""))

            # 三层可见性判断
            if self._can_access(
                visibility=visibility,
                space_id=int(space_id) if space_id else 0,
                creator_id=creator_id,
                user_id=user_id,
                department_id=department_id,
                department_path=department_path,
                allowed_space_ids=allowed_space_ids,
            ):
                filtered.append(chunk)

        if len(filtered) < len(chunks):
            logger.debug(
                f"[PermissionFilter] 过滤: {len(chunks)} -> {len(filtered)} "
                f"(移除 {len(chunks) - len(filtered)} 条未授权 chunk)"
            )

        return filtered

    @staticmethod
    def _can_access(
        visibility: str,
        space_id: int,
        creator_id: str,
        user_id: str,
        department_id: int,
        department_path: str,
        allowed_space_ids: list[int],
    ) -> bool:
        """判断用户是否有权访问某个 chunk。"""
        # public: 全员可访问
        if visibility == "public":
            return True

        # 预计算白名单兜底
        if space_id in allowed_space_ids:
            return True

        # private: 仅创建者
        if visibility == "private":
            return str(creator_id) == str(user_id)

        # department: 同部门（Python 侧用 allowed_space_ids 兜底，
        # 精确的部门树判断由 Java 预计算完成）
        if visibility == "department":
            return space_id in allowed_space_ids

        return False


permission_filter = PermissionFilter()
