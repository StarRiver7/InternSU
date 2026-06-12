"""Schema 加载器 - 通过 Java 端 HTTP 接口获取业务库表结构，为 LLM 构建模式上下文。

架构变更 (v5):
  - 不再直连 MySQL。Python 通过 HTTP GET /api/sql/schema (Java) 获取完整 Schema。
  - 枚举值提示（value hints）改用静态回退，业务表字段取值稳定，无需动态采样。
"""

from dataclasses import dataclass, field
import httpx
from app.core.config import settings
from app.sql_agent.schema_cache import schema_cache
from app.core.logger import get_logger

logger = get_logger(__name__)

BUSINESS_DB = "internsu_business"

EXPOSED_TABLES = [
    "hr_candidate", "hr_department", "hr_interview", "hr_position",
    "oa_attendance", "oa_department", "oa_employee", "oa_project", "oa_task",
]

TABLE_DESCRIPTIONS = {
    "hr_candidate": "候选人表（HR模块）。记录所有应聘者的基本信息、简历、技能、教育经历、状态等",
    "hr_department": "HR部门组织表。树形结构，支持多级部门。包含部门名称、编制人数、在职人数",
    "hr_interview": "面试记录表（HR模块）。每次面试的轮次、类型、面试官、结果、评分、反馈",
    "hr_position": "招聘职位表（HR模块）。职位名称、所属部门、职级、薪资范围、要求、职责、状态",
    "oa_attendance": "考勤记录表（OA模块）。员工每日打卡时间、请假类型、工时、备注",
    "oa_department": "OA部门组织表。树形结构，包含部门名称、上级部门、负责人、状态",
    "oa_employee": "员工表（OA模块）。工号、姓名、邮箱、手机、部门、职位、在职状态、入职/离职日期",
    "oa_project": "项目表（OA模块）。项目名称、描述、负责人、所属部门、状态、起止日期、预算",
    "oa_task": "任务表（OA模块）。任务标题、描述、所属项目、负责人、优先级、状态、截止日期、进度",
}

EXCLUDED_COLUMNS = {
    "password", "is_deleted", "creator_id", "ip_address", "user_agent",
    "avatar_url", "last_login_time", "last_login_ip", "file_path", "file_hash",
    "error_msg", "fail_reason", "config", "parameters_schema", "system_template",
    "user_template", "variables_schema", "step_detail", "update_time",
}


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    column_key: str
    column_comment: str
    ordinal: int


@dataclass
class TableInfo:
    name: str
    comment: str
    columns: list = field(default_factory=list)


class SchemaLoader:
    """Schema 加载器 —— 通过 Java HTTP API 获取业务库结构。"""

    def __init__(self):
        self._base_url = settings.java_service_url.rstrip("/")
        self._api_key = settings.java_service_api_key

    # ========== 公共入口 ==========

    async def load(self) -> dict:
        """加载业务库 Schema（优先缓存）。"""
        cached = schema_cache.get()
        if cached:
            return cached
        tables = await self._load_from_java()
        if not tables:
            tables = self._static_fallback()
        schema_cache.set(tables)
        return tables

    # ========== Java HTTP 加载 ==========

    async def _load_from_java(self) -> dict:
        """通过 HTTP GET /api/sql/schema 从 Java 端获取完整 Schema。

        Java 返回格式:
          {"code": 200, "data": {"tables": [{ "tableName", "tableComment",
            "columns": [{ "columnName", "dataType", "isNullable",
                         "isPrimaryKey", "columnComment" }] }], ... }}

        Returns:
            {table_name: TableInfo} 字典，仅包含 EXPOSED_TABLES 中的表。
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/api/sql/schema",
                    headers={
                        "X-Api-Key": self._api_key,
                        "Content-Type": "application/json",
                    },
                )

            if resp.status_code != 200:
                logger.warning(
                    "Java Schema 接口返回 HTTP %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return {}

            body = resp.json()
            # Java Result<T> 格式: {"code": 200, "data": {...}}
            data = body.get("data", body)
            java_tables = data.get("tables", [])

            tables: dict = {}
            for jt in java_tables:
                table_name = jt.get("tableName", "")
                if table_name not in EXPOSED_TABLES:
                    continue

                columns = []
                for idx, jc in enumerate(jt.get("columns", [])):
                    columns.append(ColumnInfo(
                        name=jc.get("columnName", ""),
                        data_type=jc.get("dataType", ""),
                        is_nullable=jc.get("isNullable", False),
                        column_key="PRI" if jc.get("isPrimaryKey") else "",
                        column_comment=jc.get("columnComment", ""),
                        ordinal=idx + 1,
                    ))

                tables[table_name] = TableInfo(
                    name=table_name,
                    comment=jt.get("tableComment", ""),
                    columns=columns,
                )

            logger.info(
                "已从 Java 端加载 Schema: %d 个表 (共 %d 个)",
                len(tables),
                len(java_tables),
            )
            return tables

        except httpx.TimeoutException:
            logger.warning("Java Schema 接口超时，回退静态 Schema")
            return {}
        except httpx.ConnectError:
            logger.warning("无法连接 Java 服务，回退静态 Schema")
            return {}
        except Exception as e:
            logger.warning("Java Schema 加载失败: %s", e)
            return {}

    # ========== 静态回退 ==========

    def _static_fallback(self) -> dict:
        """当 Java 接口不可用时，使用硬编码的静态 Schema 作为兜底。"""
        tables = {}
        tables["hr_candidate"] = TableInfo("hr_candidate", "候选人表", [
            ColumnInfo("id", "bigint", False, "PRI", "候选人ID", 1),
            ColumnInfo("name", "varchar", False, "", "姓名", 2),
            ColumnInfo("phone", "varchar", True, "", "手机号", 3),
            ColumnInfo("email", "varchar", True, "", "邮箱", 4),
            ColumnInfo("position_id", "bigint", True, "MUL", "应聘职位ID", 5),
            ColumnInfo("source", "varchar", True, "", "来源渠道", 6),
            ColumnInfo("resume_url", "varchar", True, "", "简历地址", 7),
            ColumnInfo("skills", "text", True, "", "技能标签", 8),
            ColumnInfo("education", "varchar", True, "", "最高学历", 9),
            ColumnInfo("experience", "text", True, "", "工作经历", 10),
            ColumnInfo("status", "varchar", False, "", "状态: 待筛选/筛选通过/面试中/已录用/已拒绝", 11),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 12),
        ])
        tables["hr_department"] = TableInfo("hr_department", "HR部门表", [
            ColumnInfo("id", "bigint", False, "PRI", "部门ID", 1),
            ColumnInfo("name", "varchar", False, "", "部门名称", 2),
            ColumnInfo("parent_id", "bigint", True, "MUL", "上级部门ID", 3),
            ColumnInfo("head_count", "int", False, "", "编制人数", 4),
            ColumnInfo("current_count", "int", False, "", "当前在职人数", 5),
            ColumnInfo("description", "text", True, "", "部门描述", 6),
            ColumnInfo("status", "tinyint", False, "", "1=正常 0=禁用", 7),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 8),
        ])
        tables["hr_interview"] = TableInfo("hr_interview", "面试记录表", [
            ColumnInfo("id", "bigint", False, "PRI", "面试ID", 1),
            ColumnInfo("candidate_id", "bigint", False, "MUL", "候选人ID", 2),
            ColumnInfo("position_id", "bigint", False, "MUL", "职位ID", 3),
            ColumnInfo("interviewer_id", "bigint", True, "", "面试官ID(oa_employee)", 4),
            ColumnInfo("round", "int", False, "", "面试轮次: 1/2/3", 5),
            ColumnInfo("type", "varchar", False, "", "面试类型: 初试/复试/技术面/HR面/终面", 6),
            ColumnInfo("status", "varchar", False, "", "状态: 待面试/已面试/通过/未通过", 7),
            ColumnInfo("interview_date", "datetime", True, "", "面试时间", 8),
            ColumnInfo("result", "varchar", True, "", "结果: pass/fail/pending", 9),
            ColumnInfo("score", "int", True, "", "评分 0-100", 10),
            ColumnInfo("feedback", "text", True, "", "面试反馈", 11),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 12),
        ])
        tables["hr_position"] = TableInfo("hr_position", "招聘职位表", [
            ColumnInfo("id", "bigint", False, "PRI", "职位ID", 1),
            ColumnInfo("name", "varchar", False, "", "职位名称", 2),
            ColumnInfo("department_id", "bigint", True, "MUL", "所属部门ID", 3),
            ColumnInfo("level", "varchar", True, "", "职级: 初级/中级/高级/资深/管理", 4),
            ColumnInfo("salary_min", "int", True, "", "最低薪资", 5),
            ColumnInfo("salary_max", "int", True, "", "最高薪资", 6),
            ColumnInfo("requirements", "text", True, "", "任职要求", 7),
            ColumnInfo("responsibilities", "text", True, "", "岗位职责", 8),
            ColumnInfo("status", "varchar", False, "", "状态: 招聘中/暂停招聘/已关闭", 9),
            ColumnInfo("open_date", "date", True, "", "开放日期", 10),
            ColumnInfo("close_date", "date", True, "", "截止日期", 11),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 12),
        ])
        tables["oa_attendance"] = TableInfo("oa_attendance", "考勤记录表", [
            ColumnInfo("id", "bigint", False, "PRI", "考勤ID", 1),
            ColumnInfo("employee_id", "bigint", False, "MUL", "员工ID", 2),
            ColumnInfo("date", "date", False, "", "日期", 3),
            ColumnInfo("check_in_time", "datetime", True, "", "签到时间", 4),
            ColumnInfo("check_out_time", "datetime", True, "", "签退时间", 5),
            ColumnInfo("status", "varchar", False, "", "状态: 正常/迟到/早退/旷工/请假", 6),
            ColumnInfo("leave_type", "varchar", True, "", "请假类型: 事假/病假/年假/调休", 7),
            ColumnInfo("hours", "decimal", True, "", "工时/请假小时数", 8),
            ColumnInfo("remark", "varchar", True, "", "备注", 9),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 10),
        ])
        tables["oa_department"] = TableInfo("oa_department", "OA部门表", [
            ColumnInfo("id", "bigint", False, "PRI", "部门ID", 1),
            ColumnInfo("name", "varchar", False, "", "部门名称", 2),
            ColumnInfo("parent_id", "bigint", True, "MUL", "上级部门ID", 3),
            ColumnInfo("manager_id", "bigint", True, "", "部门负责人ID(oa_employee)", 4),
            ColumnInfo("description", "text", True, "", "部门描述", 5),
            ColumnInfo("status", "tinyint", False, "", "1=正常 0=禁用", 6),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 7),
        ])
        tables["oa_employee"] = TableInfo("oa_employee", "员工表", [
            ColumnInfo("id", "bigint", False, "PRI", "员工ID", 1),
            ColumnInfo("employee_no", "varchar", False, "UNI", "工号", 2),
            ColumnInfo("name", "varchar", False, "", "姓名", 3),
            ColumnInfo("email", "varchar", True, "", "邮箱", 4),
            ColumnInfo("phone", "varchar", True, "", "手机号", 5),
            ColumnInfo("department_id", "bigint", True, "MUL", "所属部门ID", 6),
            ColumnInfo("position", "varchar", True, "", "职位名称", 7),
            ColumnInfo("status", "varchar", False, "", "状态: 在职/离职/试用期", 8),
            ColumnInfo("hire_date", "date", True, "", "入职日期", 9),
            ColumnInfo("leave_date", "date", True, "", "离职日期", 10),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 11),
        ])
        tables["oa_project"] = TableInfo("oa_project", "项目表", [
            ColumnInfo("id", "bigint", False, "PRI", "项目ID", 1),
            ColumnInfo("name", "varchar", False, "", "项目名称", 2),
            ColumnInfo("description", "text", True, "", "项目描述", 3),
            ColumnInfo("manager_id", "bigint", True, "MUL", "项目经理ID(oa_employee)", 4),
            ColumnInfo("department_id", "bigint", True, "MUL", "所属部门ID", 5),
            ColumnInfo("status", "varchar", False, "", "状态: 待启动/进行中/已完成/已终止", 6),
            ColumnInfo("start_date", "date", True, "", "开始日期", 7),
            ColumnInfo("end_date", "date", True, "", "结束日期", 8),
            ColumnInfo("budget", "decimal", True, "", "预算(元)", 9),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 10),
        ])
        tables["oa_task"] = TableInfo("oa_task", "任务表", [
            ColumnInfo("id", "bigint", False, "PRI", "任务ID", 1),
            ColumnInfo("title", "varchar", False, "", "任务标题", 2),
            ColumnInfo("description", "text", True, "", "任务描述", 3),
            ColumnInfo("project_id", "bigint", True, "MUL", "所属项目ID", 4),
            ColumnInfo("assignee_id", "bigint", True, "MUL", "负责人ID(oa_employee)", 5),
            ColumnInfo("priority", "varchar", False, "", "优先级: 高/中/低/紧急", 6),
            ColumnInfo("status", "varchar", False, "", "状态: 待处理/进行中/已完成/已取消", 7),
            ColumnInfo("due_date", "date", True, "", "截止日期", 8),
            ColumnInfo("progress", "int", False, "", "进度百分比 0-100", 9),
            ColumnInfo("create_time", "datetime", False, "", "创建时间", 10),
        ])
        logger.info(f"静态 Schema 回退: {len(tables)} 个业务表")
        return tables

    # ========== 上下文构建 ==========

    def build_context(
        self,
        tables: dict | None = None,
        target_tables: list | None = None,
    ) -> str:
        """根据 Schema 构建 LLM 可读的表结构上下文。"""
        tables = tables or {}
        src = target_tables or EXPOSED_TABLES
        lines_list = ["## 业务数据库结构 (internsu_business)"]
        for tbl_name in src:
            info = tables.get(tbl_name)
            if not info:
                continue
            desc = TABLE_DESCRIPTIONS.get(tbl_name, info.comment or tbl_name)
            lines_list.append(f"- **{tbl_name}**: {desc}")
            col_lines = []
            for col in info.columns[:12]:
                if col.name in EXCLUDED_COLUMNS:
                    continue
                nullable = "?" if col.is_nullable else ""
                pk = " PK" if col.column_key == "PRI" else ""
                comment = f" -- {col.column_comment}" if col.column_comment else ""
                col_lines.append(
                    f"    {col.name} ({col.data_type}{nullable}{pk}){comment}"
                )
            if col_lines:
                lines_list.extend(col_lines)
            lines_list.append("")
        return "\n".join(lines_list)

    def get_join_hints(self) -> str:
        """返回业务表之间的关联关系提示。"""
        return (
            "## 表关联提示\n"
            "- hr_candidate.position_id -> hr_position.id (候选人应聘职位)\n"
            "- hr_position.department_id -> hr_department.id (职位所属部门)\n"
            "- hr_interview.candidate_id -> hr_candidate.id (面试关联候选人)\n"
            "- hr_interview.position_id -> hr_position.id (面试关联职位)\n"
            "- hr_interview.interviewer_id -> oa_employee.id (面试官)\n"
            "- oa_attendance.employee_id -> oa_employee.id (考勤关联员工)\n"
            "- oa_employee.department_id -> oa_department.id (员工所属部门)\n"
            "- oa_department.parent_id -> oa_department.id (部门上下级)\n"
            "- oa_department.manager_id -> oa_employee.id (部门负责人)\n"
            "- oa_project.department_id -> oa_department.id (项目所属部门)\n"
            "- oa_project.manager_id -> oa_employee.id (项目经理)\n"
            "- oa_task.project_id -> oa_project.id (任务关联项目)\n"
            "- oa_task.assignee_id -> oa_employee.id (任务负责人)\n"
        )

    # ========== 枚举值提示（静态） ==========
    # 业务表枚举字段的取值稳定，直接硬编码避免额外 HTTP 调用。
    # 如需动态更新，可通过 Java /api/sql/execute 查询 DISTINCT 值。

    def _get_value_hints(self) -> str:
        """返回字段枚举值提示（静态）。"""
        return (
            "## 字段值提示（WHERE 条件请使用这些精确值）\n"
            "- oa_employee.status: '在职' / '离职' / '试用期'\n"
            "- oa_attendance.status: '正常' / '迟到' / '早退' / '旷工' / '请假'\n"
            "- oa_attendance.leave_type: '事假' / '病假' / '年假' / '调休'\n"
            "- oa_project.status: '待启动' / '进行中' / '已完成' / '已终止'\n"
            "- oa_task.status: '待处理' / '进行中' / '已完成' / '已取消'\n"
            "- oa_task.priority: '高' / '中' / '低' / '紧急'\n"
            "- hr_candidate.status: '待筛选' / '筛选通过' / '面试中' / '已录用' / '已拒绝'\n"
            "- hr_position.status: '招聘中' / '暂停招聘' / '已关闭'\n"
            "- hr_position.level: '初级' / '中级' / '高级' / '资深' / '管理'\n"
            "- hr_interview.status: '待面试' / '已面试' / '通过' / '未通过'\n"
            "- hr_interview.type: '初试' / '复试' / '技术面' / 'HR面' / '终面'\n"
        )

    # ========== 综合上下文入口 ==========

    async def get_schema_context(self, target_tables: list | None = None) -> str:
        """获取完整的 Schema 上下文文本（用于注入 LLM 提示词）。

        包含: 表结构 + 关联提示 + 枚举值提示。
        """
        schema = await self.load()
        ctx = self.build_context(schema, target_tables)
        ctx += "\n" + self.get_join_hints()
        ctx += "\n" + self._get_value_hints()

        cached = schema_cache.get_context()
        if not cached:
            schema_cache.set_context(ctx)
        return ctx


# 全局单例
schema_loader = SchemaLoader()
