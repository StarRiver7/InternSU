import asyncio
from datetime import datetime, timedelta
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings
import httpx

async def diag2():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"
    token = await client._ensure_token()

    now = datetime.now()
    start = now - timedelta(hours=48)
    start_int = int(start.timestamp() * 1000)
    end_int = int(now.timestamp() * 1000)

    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        # Try with integer params
        resp = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 20,
                "start_time": start_int,
                "end_time": end_int,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        print(f"Int params: {len(items)} messages, code={data.get('code')}, msg={data.get('msg')}")
        for item in items[:3]:
            print(f"  msg_type={item.get('msg_type')}, create_time={item.get('create_time')}")

        # Try with sort_type
        resp2 = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 20,
                "start_time": str(start_int),
                "end_time": str(end_int),
                "sort_type": "ByCreateTimeAsc",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data2 = resp2.json()
        items2 = data2.get("data", {}).get("items", [])
        print(f"\nStr params + sort: {len(items2)} messages, code={data2.get('code')}, msg={data2.get('msg')}")
        for item in items2[:3]:
            print(f"  msg_type={item.get('msg_type')}, create_time={item.get('create_time')}")

    await client.close()

asyncio.run(diag2())
