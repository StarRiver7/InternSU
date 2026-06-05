import asyncio
from datetime import datetime, timedelta
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings
import httpx

async def diag3():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"
    token = await client._ensure_token()

    # Try very wide range: messages from 2020 to 2030
    start_wide = "1577836800000"  # 2020-01-01 00:00:00 UTC
    end_wide = "1893456000000"    # 2030-01-01 00:00:00 UTC

    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        resp = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 5,
                "start_time": start_wide,
                "end_time": end_wide,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"Full URL: {resp.url}")
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        print(f"Wide range ({start_wide[:10]}...{end_wide[:10]}): {len(items)} messages, code={data.get('code')}, msg={data.get('msg')}")

    await client.close()

asyncio.run(diag3())
