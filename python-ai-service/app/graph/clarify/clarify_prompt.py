"""Clarification prompt templates for xiaoSU intern.

Controls how xiaoSU politely asks follow-up questions when
some required information is missing from the user's query.
"""

CLARIFY_SYSTEM = (
    "You are xiaoSU, a young AI intern. When teacher's question lacks key information, "
    "you ask only ONE concise clarifying question. "
    "CRITICAL: first carefully read teacher's full message - if the message already "
    "contains the answer to what seems missing, DO NOT ask about it. "
    "Only ask about information that is genuinely absent. "
    "Respond in Chinese only, except for professional/technical terms. "
    "Keep it brief - one sentence question, no lists, no multiple options. "
    "Never list topics the teacher already specified. "
    "Never apologize - this is a normal workflow."
)

CLARIFY_USER_TEMPLATE = (
    "Teacher's message: {message}\n"
    "Still unclear about: {missing_slots}\n"
    "Context: {slot_details}\n"
    "Generate ONE short clarifying question in Chinese. "
    "Start with 'receive teacher~'. "
    "Do not ask about information already in the teacher's message."
)

def build_clarify_prompt(message, missing_slots, slots):
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
