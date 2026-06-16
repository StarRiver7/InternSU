"""
一键启动服务 + 运行性能测试。

使用方式:
  python tests/benchmark/start_and_bench.py

会自动:
  1. 启动 Python AI 服务 (后台)
  2. 等待服务就绪
  3. 运行首 Token 延迟测试
  4. 运行并发压测
  5. 输出结果
  6. 关闭服务
"""

import subprocess
import sys
import time
import os
import signal

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))


def wait_for_service(url="http://localhost:8000/ai/health", timeout=30):
    """等待服务启动。"""
    import httpx
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    print("\n" + "=" * 60)
    print("  InternSU 一键启动 + 性能压测")
    print("=" * 60)

    # 1. 启动服务
    print("\n[1/4] 启动 Python AI 服务...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"  服务 PID: {proc.pid}")

    try:
        # 2. 等待服务就绪
        print("\n[2/4] 等待服务启动...")
        if not wait_for_service(timeout=60):
            print("  ❌ 服务启动超时!")
            proc.terminate()
            sys.exit(1)
        print("  ✅ 服务已就绪")

        # 3. 运行性能测试
        print("\n[3/4] 运行性能测试...")
        bench_script = os.path.join(BENCHMARK_DIR, "bench_first_token.py")
        result = subprocess.run(
            [sys.executable, bench_script],
            cwd=PROJECT_DIR,
        )

        # 4. 输出 Locust 使用说明
        print("\n[4/4] Locust 负载测试（可选）:")
        print(f"  locust -f {os.path.join(BENCHMARK_DIR, 'locust_load_test.py')} --host=http://localhost:8000")
        print("  打开 http://localhost:8089 配置: Users=120, Spawn rate=10, Run time=60s")

    except KeyboardInterrupt:
        print("\n\n  ⚠️  用户中断")
    finally:
        # 关闭服务
        print(f"\n  关闭服务 (PID={proc.pid})...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("  ✅ 服务已关闭")


if __name__ == "__main__":
    main()
