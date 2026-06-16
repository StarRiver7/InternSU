"""
快速启动脚本 — 一键运行所有性能测试。

使用方式:
  python tests/benchmark/run_all_benchmarks.py

前提:
  - Python AI 服务已在 localhost:8000 启动
  - DeepSeek API 余额充足
"""

import subprocess
import sys
import time
import os

BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(BENCHMARK_DIR))


def check_service():
    """检查服务是否运行。"""
    import httpx
    try:
        resp = httpx.get("http://localhost:8000/ai/health", timeout=5.0)
        if resp.status_code == 200:
            print("  ✅ 服务运行正常 (localhost:8000)")
            return True
    except Exception:
        pass

    print("  ❌ 服务未运行！请先启动:")
    print("     cd python-ai-service")
    print("     uvicorn app.main:app --reload --port 8000")
    return False


def run_benchmarks():
    """运行基准测试。"""
    print("\n" + "=" * 60)
    print("  InternSU 性能基准测试套件")
    print("=" * 60)

    # 1. 检查服务
    if not check_service():
        sys.exit(1)

    # 2. 运行首 Token 延迟测试
    print("\n" + "-" * 60)
    print("  Phase 1: 首 Token 延迟 + 并发压测")
    print("-" * 60)

    bench_script = os.path.join(BENCHMARK_DIR, "bench_first_token.py")
    result = subprocess.run(
        [sys.executable, bench_script],
        cwd=PROJECT_DIR,
    )

    # 3. 运行 Locust 压测（可选）
    print("\n" + "-" * 60)
    print("  Phase 2: Locust 负载测试（可选，Ctrl+C 停止）")
    print("-" * 60)
    print("  启动命令:")
    print(f"  locust -f {os.path.join(BENCHMARK_DIR, 'locust_load_test.py')} --host=http://localhost:8000")
    print("  然后打开 http://localhost:8089 配置并发数")
    print("  推荐配置: Users=120, Spawn rate=10, Run time=60s")


if __name__ == "__main__":
    run_benchmarks()
