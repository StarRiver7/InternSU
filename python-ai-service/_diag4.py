import asyncio
import json
import httpx
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings

async def find_mentions():
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )
    chat_id = "oc_07c6f5370950fd608a9196a70f44020c"
    token = await client._ensure_token()
    
    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        page_token = None
        seen = 0
        while seen < 50:
            params = {
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 20,
                "sort_type": "ByCreateTimeDesc",
            }
            if page_token:
                params["page_token"] = page_token
            resp = await http.get("/open-apis/im/v1/messages", params=params, headers={"Authorization": f"Bearer {token}"})
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            for item in items:
                seen += 1
                mentions = item.get("mentions")
                if mentions:
                    print(f"\nMessage {seen} HAS mentions:")
                    print(f"  msg_type: {item.get('msg_type')}")
                    print(f"  mentions: {json.dumps(mentions, ensure_ascii=False, indent=2)}")
                    print(f"  body content: {item.get('body', {}).get('content', '')[:100]}")
                    return
            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("page_token")
        print(f"Checked {seen} messages, no mentions found")
    
    await client.close()

asyncio.run(find_mentions())
