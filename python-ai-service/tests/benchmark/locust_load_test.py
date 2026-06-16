"""
Locust 负载测试 — 测量 QPS、P99 延迟、吞吐量。

使用方式:
  1. 启动 Python AI 服务: uvicorn app.main:app --port 8000
  2. 运行: locust -f tests/benchmark/locust_load_test.py --host=http://localhost:8000
  3. 浏览器打开 http://localhost:8089 配置并发数和启动压测

  或无头模式:
  locust -f tests/benchmark/locust_load_test.py --host=http://localhost:8000 \
    --headless -u 120 -r 10 --run-time 60s --csv=results
"""

import json
import random
import time
from locust import HttpUser, task, between, events

API_KEY = "dev-api-key"

# ── 测试数据：覆盖不同意图类型的查询 ──────────────────────────────
CHAT_QUERIES = [
    "你好，你是谁？",
    "今天天气怎么样？",
    "帮我翻译一句话",
    "推荐一本好书",
    "你好小SU",
]

RAG_QUERIES = [
    "学校有几个社团？",
    "考试时能不能带手机？",
    "请假需要什么手续？",
    "校训是什么？",
    "心理咨询室什么时候开放？",
    "迟到怎么处理？",
    "暑假从什么时候开始？",
    "消防安全有什么要求？",
    "作业有什么要求？",
    "放学时间是几点？",
]

ALL_QUERIES = CHAT_QUERIES + RAG_QUERIES


class ChatUser(HttpUser):
    """模拟用户发送聊天请求（SSE 流式）。"""

    wait_time = between(1, 3)  # 用户间隔 1-3 秒

    def on_start(self):
        """用户启动时生成一个 conversation_id。"""
        self.conversation_id = f"bench_{random.randint(100000, 999999)}"
        self.user_id = f"bench_user_{random.randint(1, 100)}"

    @task(3)
    def chat_stream(self):
        """SSE 流式聊天（主要测试场景）。"""
        query = random.choice(ALL_QUERIES)
        payload = {
            "message": query,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "stream": True,
        }

        start_time = time.time()
        first_token_time = None
        token_count = 0
        error = None

        try:
            with self.client.post(
                "/ai/chat",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": API_KEY,
                },
                stream=True,
                catch_response=True,
                name="/ai/chat [SSE]",
            ) as response:
                if response.status_code != 200:
                    response.failure(f"HTTP {response.status_code}")
                    return

                for line in response.iter_lines():
                    if not line:
                        continue

                    # 解析 SSE 事件
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: ") and first_token_time is None:
                        try:
                            data = json.loads(line[6:])
                            if event_type == "token":
                                first_token_time = time.time()
                                token_count += 1
                        except json.JSONDecodeError:
                            pass
                    elif line.startswith("data: ") and event_type == "token":
                        token_count += 1

                # 计算指标
                total_time = time.time() - start_time
                ttfb = (first_token_time - start_time) if first_token_time else total_time

                # 添加自定义指标
                events.request.fire(
                    request_type="SSE",
                    name="/ai/chat [first_token]",
                    response_time=ttfb * 1000,  # ms
                    response_length=0,
                    exception=None,
                    context={},
                )

        except Exception as e:
            total_time = time.time() - start_time
            events.request.fire(
                request_type="SSE",
                name="/ai/chat [error]",
                response_time=total_time * 1000,
                response_length=0,
                exception=e,
                context={},
            )

    @task(1)
    def chat_non_stream(self):
        """非流式聊天（对照组）。"""
        query = random.choice(ALL_QUERIES)
        payload = {
            "message": query,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "stream": False,
        }

        with self.client.post(
            "/ai/chat",
            json=payload,
            headers={"X-Api-Key": API_KEY},
            name="/ai/chat [json]",
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def health_check(self):
        """健康检查接口（低开销基准）。"""
        with self.client.get("/ai/health", headers={"X-Api-Key": API_KEY}, name="/ai/health") as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
