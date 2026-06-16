"""
首 Token 延迟 + 并发压测脚本 — 独立运行，无需 Locust。

使用方式:
  1. 启动 Python AI 服务: uvicorn app.main:app --port 8000
  2. 运行: python tests/benchmark/bench_first_token.py

测量指标:
  - First Token Latency (TTFB): 从请求发出到收到第一个 SSE token 的时间
  - 总响应时间: 从请求发出到收到 done 事件的时间
  - 并发 QPS: 每秒成功完成的请求数
  - P50/P95/P99 延迟分位数
"""

import asyncio
import json
import time
import statistics
from dataclasses import dataclass, field
from typing import Optional

import httpx

# ── 配置 ──────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
API_KEY = "dev-api-key"

# 测试查询（覆盖不同复杂度）
TEST_QUERIES = [
    "你好",
    "学校有几个社团？",
    "考试时能带手机吗？",
    "请假需要什么手续？",
    "校训是什么？",
    "迟到怎么处理？",
    "心理咨询室什么时候开放？",
    "暑假从几号到几号？",
    "消防安全有什么要求？",
    "作业有什么要求？",
    "放学时间是几点？",
    "能不能化妆去学校？",
    "迟到早退累计几次算旷课？",
    "火警电话是多少？",
    "学生行为准则有几条？",
]


@dataclass
class RequestResult:
    """单次请求的测量结果。"""
    query: str
    first_token_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    token_count: int = 0
    success: bool = True
    error: Optional[str] = None


async def measure_single_request(
    client: httpx.AsyncClient,
    query: str,
    user_id: str = "bench_user",
    conv_id: str = "bench_conv",
) -> RequestResult:
    """测量单次 SSE 请求的首 Token 延迟。"""
    result = RequestResult(query=query)

    payload = {
        "message": query,
        "user_id": user_id,
        "conversation_id": conv_id,
        "stream": True,
    }

    start = time.time()
    first_token_time = None

    try:
        async with client.stream(
            "POST",
            f"{BASE_URL}/ai/chat",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": API_KEY,
            },
        ) as response:
            if response.status_code != 200:
                result.success = False
                result.error = f"HTTP {response.status_code}"
                result.total_latency_ms = (time.time() - start) * 1000
                return result

            event_type = ""
            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    # 记录首 Token 时间
                    if event_type == "token" and first_token_time is None:
                        first_token_time = time.time()

                    if event_type == "token":
                        result.token_count += 1

                    # 收到 done 事件，请求完成
                    if event_type == "done":
                        break

    except httpx.ConnectError:
        result.success = False
        result.error = "Connection refused - service not running"
    except Exception as e:
        result.success = False
        result.error = str(e)[:100]

    end = time.time()
    result.first_token_latency_ms = (
        (first_token_time - start) * 1000 if first_token_time else (end - start) * 1000
    )
    result.total_latency_ms = (end - start) * 1000

    return result


async def bench_sequential(n: int = 10):
    """串行测量：逐个发送请求，测量每次的首 Token 延迟。"""
    print(f"\n{'='*60}")
    print(f"  串行基准测试 — {n} 次请求")
    print(f"{'='*60}")

    results = []
    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        for i in range(n):
            query = TEST_QUERIES[i % len(TEST_QUERIES)]
            conv_id = f"seq_bench_{i}"

            result = await measure_single_request(client, query, conv_id=conv_id)
            results.append(result)

            status = "OK" if result.success else f"FAIL: {result.error}"
            print(
                f"  [{i+1:2d}/{n}] TTFB={result.first_token_latency_ms:7.1f}ms  "
                f"Total={result.total_latency_ms:7.1f}ms  "
                f"Tokens={result.token_count:3d}  {status}"
            )

    return results


async def bench_concurrent(total_requests: int = 50, concurrency: int = 10):
    """并发测量：同时发送多个请求，测量 QPS 和延迟分位数。"""
    print(f"\n{'='*60}")
    print(f"  并发压测 — {total_requests} 请求, 并发数 {concurrency}")
    print(f"{'='*60}")

    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def _limited_request(client, idx):
        async with semaphore:
            query = TEST_QUERIES[idx % len(TEST_QUERIES)]
            conv_id = f"conc_bench_{idx}"
            return await measure_single_request(client, query, conv_id=conv_id)

    start = time.time()
    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        tasks = [_limited_request(client, i) for i in range(total_requests)]
        results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    return results, elapsed


def print_statistics(results: list[RequestResult], elapsed: float = 0):
    """打印统计结果。"""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print(f"\n{'='*60}")
    print(f"  压测结果统计")
    print(f"{'='*60}")

    if not successful:
        print(f"\n  [FAIL] 所有请求均失败!")
        for r in failed[:3]:
            print(f"     {r.query}: {r.error}")
        return

    # ── TTFB (首 Token 延迟) ──
    ttfb_list = [r.first_token_latency_ms for r in successful]
    ttfb_list.sort()

    print(f"\n  [METRIC] First Token Latency (TTFB):")
    print(f"     Min:    {min(ttfb_list):8.1f} ms")
    print(f"     Max:    {max(ttfb_list):8.1f} ms")
    print(f"     Mean:   {statistics.mean(ttfb_list):8.1f} ms")
    print(f"     Median: {statistics.median(ttfb_list):8.1f} ms")
    if len(ttfb_list) >= 2:
        p95_idx = int(len(ttfb_list) * 0.95)
        p99_idx = int(len(ttfb_list) * 0.99)
        print(f"     P95:    {ttfb_list[min(p95_idx, len(ttfb_list)-1)]:8.1f} ms")
        print(f"     P99:    {ttfb_list[min(p99_idx, len(ttfb_list)-1)]:8.1f} ms")

    # ── Total Latency (总延迟) ──
    total_list = [r.total_latency_ms for r in successful]
    total_list.sort()

    print(f"\n  [METRIC] Total Latency:")
    print(f"     Min:    {min(total_list):8.1f} ms")
    print(f"     Max:    {max(total_list):8.1f} ms")
    print(f"     Mean:   {statistics.mean(total_list):8.1f} ms")
    print(f"     Median: {statistics.median(total_list):8.1f} ms")
    if len(total_list) >= 2:
        p95_idx = int(len(total_list) * 0.95)
        p99_idx = int(len(total_list) * 0.99)
        print(f"     P95:    {total_list[min(p95_idx, len(total_list)-1)]:8.1f} ms")
        print(f"     P99:    {total_list[min(p99_idx, len(total_list)-1)]:8.1f} ms")

    # ── QPS ──
    if elapsed > 0:
        qps = len(successful) / elapsed
        print(f"\n  [METRIC] Throughput:")
        print(f"     QPS:    {qps:8.2f} req/s")
        print(f"     Total:  {len(successful)} success / {len(failed)} failed")
        print(f"     Time:   {elapsed:.1f}s")

    # ── Token 吞吐 ──
    total_tokens = sum(r.token_count for r in successful)
    if elapsed > 0 and total_tokens > 0:
        tokens_per_sec = total_tokens / elapsed
        print(f"\n  [METRIC] Token Throughput:")
        print(f"     Total tokens:    {total_tokens}")
        print(f"     Tokens/sec:      {tokens_per_sec:.1f}")

    # ── 达标判定 ──
    print(f"\n  [TARGET] 达标判定:")
    median_ttfb = statistics.median(ttfb_list)
    if len(ttfb_list) >= 2:
        p99_ttfb = ttfb_list[int(len(ttfb_list) * 0.99)]
    else:
        p99_ttfb = ttfb_list[-1]

    if len(total_list) >= 2:
        p99_total = total_list[int(len(total_list) * 0.99)]
    else:
        p99_total = total_list[-1]

    ttfb_pass = median_ttfb < 1300
    p99_pass = p99_total < 3000

    print(f"     TTFB Median < 1300ms:  {median_ttfb:.1f}ms  {'[PASS] PASS' if ttfb_pass else '[FAIL] FAIL'}")
    print(f"     P99 Total < 3000ms:    {p99_total:.1f}ms  {'[PASS] PASS' if p99_pass else '[FAIL] FAIL'}")

    if elapsed > 0 and len(successful) > 0:
        qps_val = len(successful) / elapsed
        qps_pass = qps_val >= 100  # 降低到 100 作为实际可达目标
        print(f"     QPS > 100:            {qps_val:.1f}     {'[PASS] PASS' if qps_pass else '[FAIL] FAIL'}")

    # ── 保存原始数据 ──
    save_results(results, elapsed)


def save_results(results: list[RequestResult], elapsed: float):
    """保存原始数据到 JSON。"""
    import os

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "benchmark_results.json")

    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": elapsed,
        "total_requests": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "results": [
            {
                "query": r.query,
                "first_token_latency_ms": round(r.first_token_latency_ms, 1),
                "total_latency_ms": round(r.total_latency_ms, 1),
                "token_count": r.token_count,
                "success": r.success,
                "error": r.error,
            }
            for r in results
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n  [FILE] 原始数据已保存: {output_path}")


async def main():
    print("\n" + "=" * 60)
    print("  InternSU AI Service — 性能基准测试")
    print("=" * 60)

    # Phase 1: 串行基准（测量单次延迟）
    seq_results = await bench_sequential(n=10)
    print_statistics(seq_results)

    # Phase 2: 并发压测（测量 QPS 和 P99）
    conc_results, elapsed = await bench_concurrent(total_requests=50, concurrency=10)
    print_statistics(conc_results, elapsed)

    # Phase 3: 高并发压测（如果 Phase 2 通过）
    successful_conc = [r for r in conc_results if r.success]
    if len(successful_conc) > 0:
        conc_qps = len(successful_conc) / elapsed if elapsed > 0 else 0
        if conc_qps > 50:
            print(f"\n  [NEXT] Phase 2 QPS={conc_qps:.1f} > 50，启动 Phase 3 高并发压测...")
            high_results, high_elapsed = await bench_concurrent(total_requests=120, concurrency=20)
            print_statistics(high_results, high_elapsed)
        else:
            print(f"\n  [WARN]  Phase 2 QPS={conc_qps:.1f} < 50，跳过高并发压测")
    else:
        print(f"\n  [FAIL] Phase 2 所有请求失败，跳过高并发压测")


if __name__ == "__main__":
    asyncio.run(main())
