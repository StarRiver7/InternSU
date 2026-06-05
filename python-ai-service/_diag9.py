import asyncio
import httpx
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings

async def diag4():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"
    token = await client._ensure_token()

    # Test: only start_time, no end_time
    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        resp = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 5,
                "start_time": "1577836800000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        print(f"Only start_time: {len(items)} messages")

        resp2 = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 5,
                "end_time": "1893456000000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data2 = resp2.json()
        items2 = data2.get("data", {}).get("items", [])
        print(f"Only end_time: {len(items2)} messages")

        # Check if maybe param names are different
        resp3 = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 5,
                "query_start_time": "1577836800000",
                "query_end_time": "1893456000000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data3 = resp3.json()
        items3 = data3.get("data", {}).get("items", [])
        print(f"query_start_time/end_time: {len(items3)} messages")

    await client.close()

asyncio.run(diag4())
