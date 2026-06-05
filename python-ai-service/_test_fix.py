import asyncio
from datetime import datetime, timedelta
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings

async def quick_test():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"
    msgs = await client.fetch_messages_for_summary(chat_id=chat_id, lookback_hours=48, max_messages=100)
    print(f"Messages found: {len(msgs)}")
    for m in msgs:
        print(f"  [{m.create_time}] {m.sender_name}: {m.plain_text[:100]}")
    await client.close()

asyncio.run(quick_test())
