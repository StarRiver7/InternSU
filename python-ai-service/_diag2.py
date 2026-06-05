import asyncio
from datetime import datetime, timedelta
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings
import json

async def diagnose2():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )

    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"

    # Test 1: No time filter
    print("=== Test 1: No time filter ===")
    msgs = await client.list_messages(chat_id=chat_id, page_size=5)
    print(f"Count: {len(msgs.items)}")
    for m in msgs.items:
        print(f"  msg_type={m.msg_type}, create_time={m.create_time}, plain_text={repr(m.plain_text[:80])}")
    
    # Test 2: 24h filter 
    end = datetime.now()
    start = end - timedelta(hours=24)
    print(f"\n=== Test 2: 24h filter ===")
    print(f"  start={start.isoformat()}, end={end.isoformat()}")
    print(f"  start_ms={int(start.timestamp() * 1000)}, end_ms={int(end.timestamp() * 1000)}")
    msgs2 = await client.list_messages(chat_id=chat_id, page_size=10, start_time=start, end_time=end)
    print(f"Count: {len(msgs2.items)}")
    for m in msgs2.items:
        print(f"  msg_type={m.msg_type}, create_time={m.create_time}, plain_text={repr(m.plain_text[:80])}")

    # Test 3: fetch_messages_for_summary
    print(f"\n=== Test 3: fetch_messages_for_summary ===")
    msgs3 = await client.fetch_messages_for_summary(chat_id=chat_id, lookback_hours=24, max_messages=100)
    print(f"Count: {len(msgs3)}")
    for m in msgs3:
        print(f"  msg_type={m.msg_type}, create_time={m.create_time}, plain_text={repr(m.plain_text[:80])}")

    # Test 4: 48h filter
    start48 = end - timedelta(hours=48)
    print(f"\n=== Test 4: 48h filter ===")
    msgs48 = await client.list_messages(chat_id=chat_id, page_size=10, start_time=start48, end_time=end)
    print(f"Count: {len(msgs48.items)}")
    for m in msgs48.items:
        print(f"  msg_type={m.msg_type}, create_time={m.create_time}, plain_text={repr(m.plain_text[:80])}")

    await client.close()

asyncio.run(diagnose2())
