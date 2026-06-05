import asyncio
import json
import httpx
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings

async def see_raw():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"
    token = await client._ensure_token()
    
    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        resp = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 3,
                "sort_type": "ByCreateTimeDesc",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        for i, item in enumerate(items):
            print(f"\n--- Message {i+1} ---")
            # Print keys and types
            for k, v in item.items():
                if k == "body":
                    print(f"  body: {json.dumps(v, ensure_ascii=False)[:300]}")
                elif k == "mentions":
                    print(f"  mentions: {json.dumps(v, ensure_ascii=False)}")
                elif k == "sender":
                    print(f"  sender: {json.dumps(v, ensure_ascii=False)}")
                else:
                    print(f"  {k}: {repr(v)[:100]}")
    
    await client.close()

asyncio.run(see_raw())
