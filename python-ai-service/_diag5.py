import asyncio
from datetime import datetime, timedelta
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings

async def check():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"

    # No time filter
    msgs = await client.list_messages(chat_id=chat_id, page_size=10)
    print(f"No time filter: {len(msgs.items)} messages")
    for m in msgs.items:
        print(f"  type={m.msg_type} plain={repr(m.plain_text[:60])} time={m.create_time}")

    # Check time math
    now = datetime.now()
    print(f"\nnow: {now} (naive)")
    print(f"now.timestamp(): {now.timestamp()}")
    start = now - timedelta(hours=48)
    print(f"start (48h ago): {start}")
    print(f"start.timestamp(): {start.timestamp()}")
    print(f"start ts ms: {int(start.timestamp() * 1000)}")

    # Check message timestamp
    ts = 1780676704188
    dt = datetime.fromtimestamp(ts / 1000)
    print(f"\nmessage ts={ts}, dt={dt}")
    print(f"message ts seconds: {ts/1000}")

    # 48h filter
    msgs48 = await client.list_messages(chat_id=chat_id, page_size=20, start_time=start, end_time=now)
    print(f"\n48h filter: {len(msgs48.items)} messages")
    for m in msgs48.items:
        print(f"  type={m.msg_type} plain={repr(m.plain_text[:60])} time={m.create_time}")

    await client.close()

asyncio.run(check())
