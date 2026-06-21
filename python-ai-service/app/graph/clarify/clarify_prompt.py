"""澄清提示词模板 —— 控制小 SU 如何礼貌地追问用户。

【设计原则】
  1. 一次只问一个问题，保持简洁
  2. 仔细阅读用户消息，避免重复提问（用户已经说了"技术部"就不要再问部门）
  3. 用中文回复
  4. 以"收到老师～"开头（保持人格化风格）
  5. 不要道歉（反问是正常工作流程）

【Prompt 结构】
  System Prompt: 定义角色和行为规范
  User Prompt: 填入用户消息 + 缺失槽位 + 槽位详情，生成反问
"""

# ── 系统提示词 ─────────────────────────────────────────────────────
# 告诉 LLM 它是小 SU，遇到信息不足时应该怎么追问
CLARIFY_SYSTEM = (
    "你是小SU，一位年轻的AI实习生。当老师的问题缺少关键信息时，"
    "你只问一个简洁的澄清问题。"
    "重要：先仔细阅读老师的完整消息——如果消息中已经包含看似缺失的答案，不要询问。"
    "只询问真正缺失的信息。"
    "只用中文回复，专业/技术术语除外。"
    "保持简短——一个句子的问题，不要列表，不要多个选项。"
    "不要列出老师已经指定的主题。"
    "不要道歉——这是正常的工作流程。"
)

# ── 用户提示词模板 ────────────────────────────────────────────────
# 用变量填充后发给 LLM
# {message}: 用户的原始消息
# {missing_slots}: 缺失的槽位名称列表，如 "department, time_range"
# {slot_details}: 缺失槽位的详细描述，如 "- 部门范围: 全部 / 部门名称"
CLARIFY_USER_TEMPLATE = (
    "老师的消息：{message}\n"
    "仍不清楚的内容：{missing_slots}\n"
    "上下文：{slot_details}\n"
    "生成一个简短的中文澄清问题。"
    "以'收到老师～'开头。"
    "不要询问老师消息中已有的信息。"
)


def build_clarify_prompt(message: str, missing_slots: list, slots: list) -> str:
    """构建澄清提示词。

    将缺失的槽位信息格式化为 LLM 可理解的上下文。
    例如 missing_slots=["department", "time_range"] 会生成：
      "- 部门范围: 全部 / 部门名称
       - 时间范围: 今天 / 本周 / 本月"

    Args:
        message: 用户原始消息（如 "帮我查一下数据"）
        missing_slots: 缺失的槽位名称列表（如 ["department", "time_range"]）
        slots: 完整的槽位定义列表（用于查找每个槽位的 label 和 hint）

    Returns:
        格式化后的澄清提示词，直接传给 LLM 生成反问
    """
    slot_details = []
    for name in missing_slots:
        for s in slots:
            if s["name"] == name:
                hint = s.get("hint", "")
                label = s.get("label", name)
                slot_details.append(f"- {label}: {hint}")

    return CLARIFY_USER_TEMPLATE.format(
        message=message,
        missing_slots=", ".join(missing_slots),
        slot_details=chr(10).join(slot_details),  # 用换行符连接
    )
