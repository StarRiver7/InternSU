"""槽位管理器 — 管理对话中的槽位定义、验证和提取。

【职责】
  1. 定义不同意图的槽位模式（SLOT_SCHEMAS）
  2. 检查缺失的必填槽位
  3. 从用户回答中提取槽位值
  4. 支持多轮对话中的槽位继承

【槽位模式定义】
每个槽位包含：
  - name: 槽位名称（用于程序内部引用）
  - label: 显示标签（用于向用户展示）
  - required: 是否必填
  - type: 数据类型（str/bool等）
  - hint: 输入提示（帮助用户理解如何填写）
  - default: 默认值（非必填槽位）

【使用示例】
  slots = slot_manager.get_slots("sql_query")
  missing = slot_manager.check_missing(slots, collected_slots)
  extracted = await slot_manager.extract_slots_from_response(user_msg, slots)
"""

import json
import re
from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)

# 槽位模式定义 — 不同意图对应不同的槽位集合
SLOT_SCHEMAS = {
    "sql_query": [
        {"name": "department", "label": "部门范围", "required": True, "type": "str", "hint": "全部 / 部门名称"},
        {"name": "time_range", "label": "时间范围", "required": True, "type": "str", "hint": "今天 / 本周 / 本月"},
        {"name": "metric", "label": "指标类型", "required": True, "type": "str", "hint": "数量 / 金额 / 订单数"},
        {"name": "include_inactive", "label": "包含无效数据", "required": False, "type": "bool", "default": False},
    ],
    "rag_query": [
        {"name": "topic", "label": "主题", "required": True, "type": "str", "hint": "出差 / 入职 / 考勤"},
        {"name": "kb_scope", "label": "知识库范围", "required": False, "type": "str", "default": "公共"},
    ],
}


class SlotManager:
    """槽位管理器 — 提供槽位定义、验证和提取功能。"""

    @staticmethod
    def get_slots(intent: str) -> list:
        """获取指定意图对应的槽位定义列表。

        Args:
            intent: 意图名称（如 "sql_query", "rag_query"）

        Returns:
            槽位定义列表，每个槽位是包含 name/label/required/type/hint/default 的字典
        """
        return SLOT_SCHEMAS.get(intent, [])

    @staticmethod
    def check_missing(slots: list, collected: dict) -> list:
        """检查哪些必填槽位尚未收集。

        Args:
            slots: 槽位定义列表
            collected: 已收集的槽位值字典

        Returns:
            缺失的必填槽位名称列表
        """
        missing = []
        for s in slots:
            if s.get("required") and s["name"] not in collected:
                missing.append(s["name"])
        return missing

    @staticmethod
    def get_slot_info(slot_name: str, slots: list) -> dict:
        """根据槽位名称获取槽位详细信息。

        Args:
            slot_name: 槽位名称
            slots: 槽位定义列表

        Returns:
            槽位定义字典，如果未找到返回 None
        """
        for s in slots:
            if s["name"] == slot_name:
                return s
        return None

    @staticmethod
    async def extract_slots_from_response(user_response: str, slots: list, previous_question: str = "") -> dict:
        """从用户回答中提取槽位值。

        使用 LLM 分析用户回答，自动识别并提取已定义槽位的值。

        Args:
            user_response: 用户的回答消息
            slots: 期望提取的槽位定义列表
            previous_question: 上一轮的澄清问题（用于上下文理解）

        Returns:
            提取到的槽位值字典 {slot_name: value}
        """
        if not slots:
            return {}

        slot_names = [s["name"] for s in slots]

        # 构建 LLM 上下文：描述需要提取的槽位
        slot_descs = []
        for s in slots:
            hint = s.get("hint", "")
            slot_descs.append(f"  - {s['name']} ({s.get('label', s['name'])}): {hint}")
        slot_context = "\n".join(slot_descs)

        # 构建系统提示词
        system_msg = (
            "从用户消息中提取槽位值。\n"
            "只返回 JSON 对象，包含槽位名称作为键。\n"
            f"需要查找的槽位：\n{slot_context}\n"
            "如果某个槽位值未找到，省略该键。不要包含 null 值。\n"
            "输出示例：{\"topic\": \"入职流程\"}"
        )

        try:
            resp = await llm_gateway.chat(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"消息: {user_response}"},
                ],
                temperature=0.0,
                max_tokens=256,
            )

            # 从响应中提取 JSON 对象
            match = re.search(r"{[^}]+}", resp.content)
            if match:
                extracted = json.loads(match.group())
                # 过滤掉不在槽位列表中的键和 None 值
                return {k: v for k, v in extracted.items() if k in slot_names and v is not None}

        except Exception as e:
            logger.warning(f"[SlotManager] 槽位提取失败: {e}")

        return {}


# 全局单例实例
slot_manager = SlotManager()
