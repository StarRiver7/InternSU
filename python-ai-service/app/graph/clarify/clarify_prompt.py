"""小SU实习生的澄清提示词模板。

【功能说明】
当用户查询缺少关键信息时，控制小SU如何礼貌地提出追问问题。

【设计原则】
  - 一次只问一个问题，保持简洁
  - 仔细阅读用户消息，避免重复提问
  - 用中文回复（专业术语除外）
  - 以"收到老师～"开头
  - 不要道歉，这是正常工作流程
"""

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

    将缺失的槽位信息格式化为 LLM 可理解的上下文，生成澄清问题。

    Args:
        message: 用户原始消息
        missing_slots: 缺失的槽位名称列表
        slots: 完整的槽位定义列表

    Returns:
        格式化后的澄清提示词
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
        slot_details=chr(10).join(slot_details),
    )
