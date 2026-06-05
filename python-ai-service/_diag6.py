import asyncio
from datetime import datetime, timedelta
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings
import httpx

async def diag():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"
    token = await client._ensure_token()

    now = datetime.now()
    start = now - timedelta(hours=48)
    start_ms = str(int(start.timestamp() * 1000))
    end_ms = str(int(now.timestamp() * 1000))

    print(f"start_ms={start_ms}, end_ms={end_ms}")

    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        resp = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 20,
                "start_time": start_ms,
                "end_time": end_ms,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        print(f"API with time filter: {len(items)} messages, code={data.get('code')}, msg={data.get('msg')}")
        for item in items:
            print(f"  msg_type={item.get('msg_type')}, create_time={item.get('create_time')}")

    # Try without time filter
    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        resp = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 20,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        print(f"\nAPI without time filter: {len(items)} messages")
        for item in items:
            print(f"  msg_type={item.get('msg_type')}, create_time={item.get('create_time')}")

    await client.close()

asyncio.run(diag())
