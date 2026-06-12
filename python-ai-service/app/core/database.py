"""数据库模块 (v5 已废弃)。

v5 架构变更: Python AI 服务不再直连 MySQL。
- Schema 加载 -> Java /api/sql/schema (HTTP)
- SQL 执行   -> Java /api/sql/execute (HTTP)
- 数据访问   -> 全部由 Java 端 MyBatis Plus 管理

此文件保留仅为历史参考，不会被任何模块导入。
"""

# 已移除所有 SQLAlchemy 引擎和连接池代码。
# 如需使用，请通过 Java HTTP 接口调用。
