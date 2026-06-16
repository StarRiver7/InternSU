"""
意图识别准确率 + 多轮澄清成功率测试。

使用方式:
  1. 启动 Python AI 服务: uvicorn app.main:app --port 8000
  2. 运行: python tests/benchmark/test_intent_accuracy.py

测量指标:
  - 意图识别准确率: 正确识别 tool 类型的比例
  - 多轮澄清成功率: 模糊查询触发澄清 + 补充信息后正确执行的比例
"""

import asyncio
import json
import time
import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "dev-api-key"


# ── 意图识别测试数据（query, expected_intent）──────────────────────────
# 注意: API 返回的是 intent 字段（映射后: chat/rag/sql/clarify/agent）
INTENT_TEST_DATA = [
    # ── chat 类（15条）──
    ("你好", "chat"),
    ("你是谁", "chat"),
    ("今天天气怎么样", "chat"),
    ("帮我翻译一句话", "chat"),
    ("推荐一本好书", "chat"),
    ("1+1等于几", "chat"),
    ("讲个笑话", "chat"),
    ("你好小SU", "chat"),
    ("谢谢", "chat"),
    ("再见", "chat"),
    ("你叫什么名字", "chat"),
    ("你会做什么", "chat"),
    ("随便聊聊", "chat"),
    ("今天是星期几", "chat"),
    ("祝你开心", "chat"),

    # ── rag 类（20条）──
    ("考试时能不能带手机", "rag"),
    ("请假需要什么手续", "rag"),
    ("校训是什么", "rag"),
    ("心理咨询室什么时候开放", "rag"),
    ("迟到怎么处理", "rag"),
    ("暑假从什么时候开始", "rag"),
    ("消防安全有什么要求", "rag"),
    ("作业有什么要求", "rag"),
    ("放学时间是几点", "rag"),
    ("能不能化妆去学校", "rag"),
    ("迟到早退累计几次算旷课", "rag"),
    ("火警电话是多少", "rag"),
    ("学生行为准则有几条", "rag"),
    ("校风包括哪些方面", "rag"),
    ("考试作弊会受到什么处分", "rag"),
    ("寒假从几号到几号", "rag"),
    ("吃饭前要做什么", "rag"),
    ("学生手册里关于着装有什么规定", "rag"),
    ("社团有哪些", "rag"),
    ("学校医务室什么时候开", "rag"),

    # ── sql 类（10条）──
    ("查一下有多少学生", "sql"),
    ("本月入职了多少新员工", "sql"),
    ("帮我查一下考勤数据", "sql"),
    ("显示所有部门信息", "sql"),
    ("查询工资最高的员工", "sql"),
    ("统计一下各部门人数", "sql"),
    ("查一下请假记录", "sql"),
    ("看看最近的面试安排", "sql"),
    ("查询项目进度", "sql"),
    ("帮我拉一下数据看看", "sql"),

    # ── clarify 类（5条）──
    ("帮我查一下", "clarify"),
    ("那个文件", "clarify"),
    ("搜一下资料", "clarify"),
    ("查数据", "clarify"),
    ("看看", "clarify"),
]

# ── 多轮澄清测试数据 ──────────────────────────────────────────────
# 格式: [(轮1问题, 期望触发澄清), (轮2回答, 期望正确执行)]
# intent 字段是映射后的值: chat/rag/sql/clarify
CLARIFY_TEST_DATA = [
    # 场景1: 查数据 → 澄清 → 补充后执行SQL
    [
        {"query": "查一下数据", "expect_intent": "clarify", "round": 1},
        {"query": "查一下本月有多少新员工入职", "expect_intent": "sql", "round": 2},
    ],
    # 场景2: 搜资料 → 澄清 → 补充后检索
    [
        {"query": "搜一下", "expect_intent": "clarify", "round": 1},
        {"query": "搜一下学校的请假制度", "expect_intent": "rag", "round": 2},
    ],
    # 场景3: 帮我查 → 澄清 → 补充后执行
    [
        {"query": "帮我查", "expect_intent": "clarify", "round": 1},
        {"query": "帮我查一下考勤数据", "expect_intent": "sql", "round": 2},
    ],
]


async def call_chat(client: httpx.AsyncClient, message: str, conv_id: str = None) -> dict:
    """调用聊天接口，返回完整结果。"""
    payload = {
        "message": message,
        "user_id": "test_user",
        "conversation_id": conv_id or f"test_{int(time.time()*1000)}",
        "stream": False,
    }

    try:
        resp = await client.post(
            f"{BASE_URL}/ai/chat",
            json=payload,
            headers={"X-Api-Key": API_KEY},
            timeout=120.0,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"HTTP {resp.status_code}", "data": {}}
    except Exception as e:
        return {"error": str(e)[:100], "data": {}}


async def test_intent_accuracy():
    """测试意图识别准确率。"""
    print("\n" + "=" * 60)
    print("  Intent Recognition Accuracy Test")
    print("=" * 60)

    correct = 0
    total = 0
    errors = []
    tool_stats = {}

    async with httpx.AsyncClient(trust_env=False, timeout=120.0) as client:
        for i, (query, expected_tool) in enumerate(INTENT_TEST_DATA):
            conv_id = f"intent_test_{i}"
            result = await call_chat(client, query, conv_id)

            data = result.get("data", {})
            actual_tool = data.get("intent", "unknown")  # intent 字段
            answer = data.get("content", "")[:80]

            total += 1
            is_correct = (actual_tool == expected_tool)
            if is_correct:
                correct += 1

            # 统计每种 tool 的表现
            if expected_tool not in tool_stats:
                tool_stats[expected_tool] = {"correct": 0, "total": 0, "wrong": []}
            tool_stats[expected_tool]["total"] += 1
            if is_correct:
                tool_stats[expected_tool]["correct"] += 1
            else:
                tool_stats[expected_tool]["wrong"].append((query, actual_tool))

            status = "OK" if is_correct else "WRONG"
            print(
                f"  [{i+1:2d}/{len(INTENT_TEST_DATA)}] "
                f"Q={query[:20]:<20s} "
                f"Expected={expected_tool:<12s} "
                f"Got={actual_tool:<12s} "
                f"[{status}]"
            )

    # 输出统计
    accuracy = correct / total if total > 0 else 0
    print(f"\n  {'='*60}")
    print(f"  Intent Accuracy: {correct}/{total} = {accuracy:.1%}")
    print(f"  {'='*60}")

    # 按 tool 分类统计
    for tool, stats in tool_stats.items():
        acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        print(f"    {tool:<12s}: {stats['correct']}/{stats['total']} = {acc:.1%}")
        if stats["wrong"]:
            for q, got in stats["wrong"][:3]:
                print(f"      WRONG: '{q}' -> got '{got}'")

    return accuracy, tool_stats


async def test_multi_turn_clarify():
    """测试多轮澄清成功率。"""
    print("\n" + "=" * 60)
    print("  Multi-turn Clarification Test")
    print("=" * 60)

    total = 0
    success = 0
    results = []

    async with httpx.AsyncClient(trust_env=False, timeout=120.0) as client:
        for scenario_idx, scenario in enumerate(CLARIFY_TEST_DATA):
            conv_id = f"clarify_test_{scenario_idx}"
            scenario_ok = True

            print(f"\n  Scenario {scenario_idx + 1}:")
            for turn in scenario:
                total += 1
                query = turn["query"]
                expect_intent = turn["expect_intent"]
                round_num = turn["round"]

                result = await call_chat(client, query, conv_id)
                data = result.get("data", {})
                actual_intent = data.get("intent", "unknown")
                answer = data.get("content", "")[:100]

                is_ok = (actual_intent == expect_intent)
                if not is_ok:
                    scenario_ok = False

                status = "OK" if is_ok else "WRONG"
                print(
                    f"    Round {round_num}: Q='{query}' "
                    f"Expected={expect_intent:<12s} Got={actual_intent:<12s} [{status}]"
                )
                # 截断 answer 避免编码问题
                safe_answer = answer.encode('ascii', 'replace').decode('ascii')[:80]
                print(f"      Answer: {safe_answer}")

            if scenario_ok:
                success += 1
            results.append(scenario_ok)

    clarify_success = success / len(CLARIFY_TEST_DATA) if CLARIFY_TEST_DATA else 0
    turn_accuracy = sum(1 for r in results if r) / len(results) if results else 0

    print(f"\n  {'='*60}")
    print(f"  Clarification Scenario Success: {success}/{len(CLARIFY_TEST_DATA)} = {clarify_success:.1%}")
    print(f"  Full Scenario Accuracy: {turn_accuracy:.1%}")
    print(f"  {'='*60}")

    return clarify_success


async def main():
    print("\n" + "=" * 60)
    print("  InternSU Intent & Clarification Accuracy Test")
    print("=" * 60)

    # 1. 意图识别准确率
    intent_accuracy, tool_stats = await test_intent_accuracy()

    # 2. 多轮澄清成功率
    clarify_success = await test_multi_turn_clarify()

    # 3. 汇总报告
    print("\n" + "=" * 60)
    print("  FINAL REPORT")
    print("=" * 60)
    print(f"  Intent Recognition Accuracy:  {intent_accuracy:.1%}")
    print(f"  Multi-turn Clarify Success:    {clarify_success:.1%}")
    print("=" * 60)

    # 保存结果
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "intent_accuracy": round(intent_accuracy, 4),
        "clarify_success_rate": round(clarify_success, 4),
        "tool_breakdown": {
            tool: {
                "accuracy": round(stats["correct"] / stats["total"], 4) if stats["total"] > 0 else 0,
                "correct": stats["correct"],
                "total": stats["total"],
            }
            for tool, stats in tool_stats.items()
        },
    }

    import os
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intent_accuracy_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
