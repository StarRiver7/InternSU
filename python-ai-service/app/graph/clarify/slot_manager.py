"""槽位管理器 —— 管理对话中的槽位定义、验证和提取。

【什么是槽位？】
槽位（Slot）是用户回答中需要提取的结构化参数。
比如用户说"帮我查一下技术部本月的考勤数据"，需要提取：
  - department = "技术部"  （部门范围）
  - time_range = "本月"    （时间范围）
  - metric = "考勤"        （指标类型）

每个意图（sql_query / rag_query）有不同的槽位集合。

【工作流程】
  1. get_slots(intent)       → 根据意图获取槽位定义
  2. check_missing(slots, collected) → 检查哪些必填槽位还没收集
  3. extract_slots_from_response()  → 用 LLM 从用户消息中自动提取槽位值

【槽位定义结构】
  {
      "name": "department",      # 槽位名称（程序内部用）
      "label": "部门范围",        # 显示标签（给用户看）
      "required": True,          # 是否必填
      "type": "str",             # 数据类型
      "hint": "全部 / 部门名称",  # 输入提示
      "default": None,           # 默认值（非必填时）
  }
"""

import json
import re
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)


# ── 槽位模式定义 ──────────────────────────────────────────────────
# 不同意图对应不同的槽位集合
# sql_query: 需要部门、时间、指标三个必填参数
# rag_query: 只需要主题一个必填参数
# chat:     不需要槽位
SLOT_SCHEMAS = {
    "sql_query": [
        {
            "name": "department",
            "label": "部门范围",
            "required": True,       # 必填
            "type": "str",
            "hint": "全部 / 部门名称",  # 帮助 LLM 和用户理解这个槽位
        },
        {
            "name": "time_range",
            "label": "时间范围",
            "required": True,
            "type": "str",
            "hint": "今天 / 本周 / 本月",
        },
        {
            "name": "metric",
            "label": "指标类型",
            "required": True,
            "type": "str",
            "hint": "数量 / 金额 / 订单数",
        },
        {
            "name": "include_inactive",
            "label": "包含无效数据",
            "required": False,      # 非必填
            "type": "bool",
            "default": False,
        },
    ],
    "rag_query": [
        {
            "name": "topic",
            "label": "主题",
            "required": True,
            "type": "str",
            "hint": "出差 / 入职 / 考勤",
        },
        {
            "name": "kb_scope",
            "label": "知识库范围",
            "required": False,
            "type": "str",
            "default": "公共",
        },
    ],
}


class SlotManager:
    """槽位管理器 —— 提供槽位定义、验证和提取功能。

    核心职责：
    1. 告诉 clarify_node 需要收集哪些槽位（get_slots）
    2. 检查已收集的槽位是否满足要求（check_missing）
    3. 用 LLM 从用户消息中自动提取槽位值（extract_slots_from_response）
    """

    @staticmethod
    def get_slots(intent: str) -> list:
        """获取指定意图对应的槽位定义列表。

        Args:
            intent: 意图名称（如 "sql_query", "rag_query", "chat"）

        Returns:
            槽位定义列表。如果该意图没有定义槽位，返回空列表。
            例如 get_slots("sql_query") 返回 4 个槽位定义，
            get_slots("chat") 返回空列表。
        """
        return SLOT_SCHEMAS.get(intent, [])

    @staticmethod
    def check_missing(slots: list, collected: dict) -> list:
        """检查哪些必填槽位尚未收集。

        Args:
            slots: 槽位定义列表（从 get_slots 获取）
            collected: 已收集的槽位值字典，如 {"department": "技术部"}

        Returns:
            缺失的必填槽位名称列表。
            例如 slots 有 department(必填) 和 topic(必填)，
            collected 只有 department，则返回 ["topic"]
        """
        missing = []
        for s in slots:
            if s.get("required") and s["name"] not in collected:
                missing.append(s["name"])
        return missing

    @staticmethod
    def get_slot_info(slot_name: str, slots: list) -> dict:
        """根据槽位名称获取槽位的详细定义信息。

        Args:
            slot_name: 槽位名称（如 "department"）
            slots: 槽位定义列表

        Returns:
            槽位定义字典，包含 name/label/required/type/hint/default
            如果未找到返回 None
        """
        for s in slots:
            if s["name"] == slot_name:
                return s
        return None

    @staticmethod
    async def extract_slots_from_response(
        user_response: str,
        slots: list,
        previous_question: str = "",
    ) -> dict:
        """从用户回答中用 LLM 自动提取槽位值。

        这是 Hot-Fill 机制的核心：在要求用户补充信息之前，
        先尝试从用户消息中自动提取槽位值，减少用户交互次数。

        例如用户说"帮我查一下技术部本月的考勤"：
          LLM 提取: {"department": "技术部", "time_range": "本月", "metric": "考勤"}

        Args:
            user_response: 用户的回答消息
            slots: 期望提取的槽位定义列表
            previous_question: 上一轮的澄清问题（可选，用于上下文理解）

        Returns:
            提取到的槽位值字典 {slot_name: value}
            如果提取失败或无匹配，返回空字典 {}
        """
        if not slots:
            return {}

        slot_names = [s["name"] for s in slots]

        # 构建槽位描述文本，告诉 LLM 需要提取哪些信息
        slot_descs = []
        for s in slots:
            hint = s.get("hint", "")
            slot_descs.append(
                f"  - {s['name']} ({s.get('label', s['name'])}): {hint}"
            )
        slot_context = "\n".join(slot_descs)

        # 构建 LLM 提示词
        system_msg = (
            "从用户消息中提取槽位值。\n"
            "只返回 JSON 对象，包含槽位名称作为键。\n"
            f"需要查找的槽位：\n{slot_context}\n"
            "如果某个槽位值未找到，省略该键。不要包含 null 值。\n"
            '输出示例：{"topic": "入职流程"}'
        )

        try:
            resp = await llm_gateway.chat(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"消息: {user_response}"},
                ],
                temperature=0.0,  # 低温保证提取准确性
                max_tokens=256,
            )

            # 从 LLM 返回的文本中提取 JSON 对象
            # LLM 可能返回 "提取结果：{"department": "技术部"}" 这样的格式
            # 用正则找到第一个 {...} 的内容
            match = re.search(r"{[^}]+}", resp.content)
            if match:
                extracted = json.loads(match.group())
                # 只保留槽位定义中存在的键，且值不为 None
                return {
                    k: v
                    for k, v in extracted.items()
                    if k in slot_names and v is not None
                }

        except Exception as e:
            logger.warning(f"[SlotManager] 槽位提取失败: {e}")

        return {}


# 全局单例实例
slot_manager = SlotManager()
