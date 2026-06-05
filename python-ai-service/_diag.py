import asyncio
import json
from datetime import datetime, timedelta
from app.tools.feishu.feishu_client import FeishuClient
from app.core.config import settings
import httpx

async def diagnose():
    print("=== Feishu Message Diagnostic ===")
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
    )

    print("\n--- Chats ---")
    chats = await client.list_chats(page_size=20)
    print(f"Total chats: {len(chats.items)}")
    for c in chats.items:
        print(f"  {c.name} ({c.chat_id})")

    if not chats.items:
        print("No chats found!")
        await client.close()
        return

    chat = chats.items[0]
    chat_id = chat.chat_id

    # Raw API call
    print(f"\n--- Raw API: {chat.name} ---")
    token = await client._ensure_token()
    async with httpx.AsyncClient(base_url=settings.feishu_base_url, timeout=httpx.Timeout(30.0)) as http:
        resp = await http.get(
            "/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 10,
                "sort_type": "ByCreateTimeDesc",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        code = data.get("code", -1)
        msg = data.get("msg", "")
        print(f"HTTP {resp.status_code}, code={code}, msg={msg}")
        items = data.get("data", {}).get("items", [])
        print(f"Raw items count: {len(items)}")
        if items:
            first = items[0]
            print(f"Keys: {list(first.keys())}")
            print(f"msg_type: {first.get('msg_type')}")
            print(f"create_time: {first.get('create_time')}")
            body = first.get("body", {})
            content = body.get("content", "")
            print(f"content: {content[:200]}")
        else:
            print("NO ITEMS in response")
        print(f"has_more: {data.get('data', {}).get('has_more')}")

    await client.close()

asyncio.run(diagnose())
