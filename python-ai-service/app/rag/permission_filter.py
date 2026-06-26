"""权限过滤器 — 根据用户权限过滤检索结果。

【权限类型】
  - public: 公开文档，所有人可访问
  - private: 私有文档，仅创建者可访问
  - department: 部门文档，同部门或授权部门可访问

【过滤规则】
  1. public 文档：始终保留
  2. private 文档：仅当 creator_id == user_id 时保留
  3. department 文档：仅当 space_id 在 allowed 列表中时保留
"""

from typing import List, Dict, Any


class PermissionFilter:
    """权限过滤器 — 过滤用户无权访问的检索结果。"""

    def filter_chunks(
        self,
        chunks: List[Dict[str, Any]],
        user_id: str,
        dept_id: int,
        dept_path: str,
        allowed_spaces: List[int],
    ) -> List[Dict[str, Any]]:
        """根据用户权限过滤检索结果。

        Args:
            chunks: 检索到的 chunk 列表，每个 chunk 包含 metadata
            user_id: 当前用户 ID
            dept_id: 用户所属部门 ID
            dept_path: 用户部门路径（如 "/1/3"）
            allowed_spaces: 用户有权访问的空间 ID 列表

        Returns:
            过滤后的 chunk 列表，移除用户无权访问的结果
        """
        filtered = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            visibility = metadata.get("visibility", "public")
            creator_id = metadata.get("creator_id", "")
            space_id = metadata.get("space_id", 0)

            if self._is_allowed(visibility, creator_id, space_id, user_id, allowed_spaces):
                filtered.append(chunk)

        return filtered

    def _is_allowed(
        self,
        visibility: str,
        creator_id: str,
        space_id: int,
        user_id: str,
        allowed_spaces: List[int],
    ) -> bool:
        """判断单个 chunk 是否允许访问。

        Args:
            visibility: 文档可见性（public/private/department）
            creator_id: 文档创建者 ID
            space_id: 文档所属空间 ID
            user_id: 当前用户 ID
            allowed_spaces: 用户有权访问的空间列表

        Returns:
            是否允许访问
        """
        if visibility == "public":
            return True

        if visibility == "private":
            return creator_id == user_id

        if visibility == "department":
            return space_id in allowed_spaces

        return False


# 全局实例
permission_filter = PermissionFilter()
