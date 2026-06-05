"""
FeishuClient — Feishu Open API Client.

Encapsulates Feishu Open Platform API calls:
  - Tenant access token management (auto-refresh)
  - List chats
  - List messages with pagination and time range
  - Message content parsing
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ============================================================
# Data Models
# ============================================================

@dataclass
class FeishuMessage:
    """Parsed Feishu message entity."""
    message_id: str
    chat_id: str
    chat_name: str = ""
    sender_id: str = ""
    sender_name: str = ""
    msg_type: str = "text"
    content: str = ""
    plain_text: str = ""
    mentions: List[str] = field(default_factory=list)
    create_time: Optional[datetime] = None
    thread_id: Optional[str] = None
    parent_id: Optional[str] = None


@dataclass
class ChatInfo:
    """Chat group basic info."""
    chat_id: str
    name: str = ""
    description: str = ""
    member_count: int = 0


@dataclass
class PaginatedResult:
    """Unified pagination result."""
    items: List[Any] = field(default_factory=list)
    total: int = 0
    has_more: bool = False
    page_token: str = ""


@dataclass
class TokenCache:
    """In-memory access_token cache with TTL."""
    token: str = ""
    expires_at: float = 0.0

    @property
    def is_valid(self) -> bool:
        return bool(self.token) and time.time() < self.expires_at


# ============================================================
# FeishuClient
# ============================================================

class FeishuClient:
    """Feishu Open Platform async HTTP client.

    Handles token lifecycle, pagination, retries, and error logging.

    Usage:
        config = settings  # from app.core.config
        client = FeishuClient(
            app_id=config.feishu_app_id,
            app_secret=config.feishu_app_secret,
            base_url=config.feishu_base_url,
        )
        chats = await client.list_chats()
        messages = await client.list_messages(chat_id="oc_xxx")
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn",
        token_cache_ttl: int = 110 * 60,
        default_page_size: int = 50,
        max_retries: int = 3,
        request_timeout: float = 30.0,
    ):
        """Initialize FeishuClient.

        Args:
            app_id: Feishu app ID (from open platform).
            app_secret: Feishu app secret.
            base_url: API base URL (use open.larksuite.com for international).
            token_cache_ttl: Token cache TTL in seconds (default 110 min).
            default_page_size: Default page size for list APIs.
            max_retries: Max retry count on failure.
            request_timeout: HTTP request timeout in seconds.
        """
        if not app_id or not app_secret:
            raise ValueError("feishu_app_id and feishu_app_secret are required")

        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = base_url.rstrip("/")
        self._token_cache_ttl = token_cache_ttl
        self._default_page_size = default_page_size
        self._max_retries = max_retries
        self._request_timeout = request_timeout

        self._token_cache = TokenCache()
        self._client: Optional[httpx.AsyncClient] = None

    # ----------------------------------------------------------
    # HTTP Client (lazy init for async context)
    # ----------------------------------------------------------
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx AsyncClient (connection pool reuse)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._request_timeout),
            )
        return self._client

    # ----------------------------------------------------------
    # Token Management
    # ----------------------------------------------------------
    async def _fetch_access_token(self) -> str:
        """Call Feishu tenant_access_token API, cache the result.

        Returns:
            Access token string.

        Raises:
            RuntimeError: If token fetch fails after all retries.
        """
        client = await self._get_client()
        url = "/open-apis/auth/v3/tenant_access_token/internal"
        body = {"app_id": self._app_id, "app_secret": self._app_secret}

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    raise RuntimeError(
                        f"Feishu token API error: code={data.get('code')} "
                        f"msg={data.get('msg')}"
                    )

                token = data["tenant_access_token"]
                self._token_cache.token = token
                # Expire 10 minutes early as safety margin
                self._token_cache.expires_at = time.time() + self._token_cache_ttl
                logger.info("Feishu access_token refreshed successfully")
                return token

            except Exception as exc:
                logger.warning(
                    "Feishu token fetch attempt %d/%d failed: %s",
                    attempt, self._max_retries, exc,
                )
                if attempt == self._max_retries:
                    raise RuntimeError(
                        f"Feishu token fetch failed after {self._max_retries} attempts"
                    ) from exc
                # Exponential backoff: 2s, 4s, 8s...
                await _sleep(2 ** attempt)

        raise RuntimeError("Feishu token fetch aborted unexpectedly")

    async def _ensure_token(self) -> str:
        """Return cached token if valid, otherwise fetch new one."""
        if self._token_cache.is_valid:
            return self._token_cache.token
        return await self._fetch_access_token()

    # ----------------------------------------------------------
    # Low-level HTTP Request
    # ----------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Dict:
        """Unified HTTP request with auth, retry, and error handling.

        Args:
            method: HTTP method (GET/POST).
            path: API path (e.g. /open-apis/im/v1/chats).
            params: URL query parameters.
            json_body: JSON request body.

        Returns:
            API response data dict (extracted from Feishu standard envelope).
        """
        token = await self._ensure_token()
        client = await self._get_client()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await client.request(
                    method=method, url=path, headers=headers,
                    params=params, json=json_body,
                )
                resp.raise_for_status()
                data = resp.json()

                code = data.get("code", -1)
                if code != 0:
                    # Token expired error codes: refresh and retry once
                    if code in (99991663, 99991664, 99991665):
                        logger.info("Feishu token expired, refreshing...")
                        self._token_cache.token = ""
                        token = await self._ensure_token()
                        headers["Authorization"] = f"Bearer {token}"
                        continue
                    raise RuntimeError(
                        f"Feishu API error: code={code} msg={data.get('msg', '')}"
                    )

                return data.get("data", {})

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Feishu HTTP %d on %s (attempt %d/%d)",
                    exc.response.status_code, path, attempt, self._max_retries,
                )
                if attempt == self._max_retries:
                    raise RuntimeError(
                        f"Feishu API failed [{method} {path}]: "
                        f"HTTP {exc.response.status_code}"
                    ) from exc
                await _sleep(2 ** attempt)

            except (httpx.RequestError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Feishu API network/parse error: %s (attempt %d/%d)",
                    exc, attempt, self._max_retries,
                )
                if attempt == self._max_retries:
                    raise RuntimeError(
                        f"Feishu API failed [{method} {path}]: {exc}"
                    ) from exc
                await _sleep(2 ** attempt)

        raise RuntimeError(f"Feishu API aborted: {method} {path}")

    # ----------------------------------------------------------
    # Chat List
    # ----------------------------------------------------------
    async def list_chats(
        self,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> PaginatedResult:
        """List chats the bot belongs to.

        Args:
            page_size: Items per page (default from config).
            page_token: Pagination token for next page.
        """
        ps = page_size or self._default_page_size
        params: Dict = {"page_size": min(ps, 100)}
        if page_token:
            params["page_token"] = page_token

        data = await self._request("GET", "/open-apis/im/v1/chats", params=params)

        chats = [
            ChatInfo(
                chat_id=item.get("chat_id", ""),
                name=item.get("name", ""),
                description=item.get("description", ""),
                member_count=item.get("member_count", 0),
            )
            for item in data.get("items", [])
        ]

        return PaginatedResult(
            items=chats,
            total=-1,
            has_more=data.get("has_more", False),
            page_token=data.get("page_token", ""),
        )

    # ----------------------------------------------------------
    # Message List
    # ----------------------------------------------------------
    async def list_messages(
        self,
        chat_id: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> PaginatedResult:
        """List messages in a chat.

        Args:
            chat_id: Chat group ID.
            page_size: Items per page.
            page_token: Pagination token.
            start_time: Earliest message time (inclusive).
            end_time: Latest message time (inclusive).
        """
        ps = page_size or self._default_page_size
        params: Dict = {
            "container_id_type": "chat",
            "container_id": chat_id,
            "page_size": min(ps, 50),
        }
        if page_token:
            params["page_token"] = page_token
        if start_time:
            params["start_time"] = str(int(start_time.timestamp() * 1000))
        if end_time:
            params["end_time"] = str(int(end_time.timestamp() * 1000))

        data = await self._request(
            "GET", "/open-apis/im/v1/messages", params=params,
        )

        messages = [
            self._parse_message(raw, chat_id)
            for raw in data.get("items", [])
        ]

        return PaginatedResult(
            items=messages,
            total=-1,
            has_more=data.get("has_more", False),
            page_token=data.get("page_token", ""),
        )

    # ----------------------------------------------------------
    # Message Parsing
    # ----------------------------------------------------------
    def _parse_message(self, raw: Dict, default_chat_id: str) -> FeishuMessage:
        """Parse raw Feishu message JSON into FeishuMessage entity.

        Extracts plain text according to msg_type:
          - text: direct text field
          - post: iterate content blocks, join text elements
          - interactive: extract card text fields
          - others: marked as [non-text]
        """
        msg_type = raw.get("msg_type", "text")
        body = raw.get("body", {})
        content = body.get("content", "")

        # Extract plain text by message type
        plain_text = _extract_plain_text(msg_type, content)

        # Extract mentions
        mentions: List[str] = []
        for m in raw.get("mentions", []):
            mid = m.get("id", "")
            if isinstance(mid, dict):
                uid = mid.get("union_id") or mid.get("open_id", "")
            else:
                uid = str(mid) if mid else ""
            if uid:
                mentions.append(uid)
        # Parse create_time (millisecond timestamp)
        create_time = None
        raw_time = raw.get("create_time", "")
        if raw_time:
            try:
                create_time = datetime.fromtimestamp(int(raw_time) / 1000)
            except (ValueError, TypeError, OSError):
                pass

        return FeishuMessage(
            message_id=raw.get("message_id", ""),
            chat_id=raw.get("chat_id", default_chat_id),
            chat_name="",
            sender_id=raw.get("sender", {}).get("id", ""),
            sender_name=raw.get("sender", {}).get("name", ""),
            msg_type=msg_type,
            content=content,
            plain_text=plain_text,
            mentions=mentions,
            create_time=create_time,
            thread_id=raw.get("thread_id"),
            parent_id=raw.get("parent_id"),
        )

    # ----------------------------------------------------------
    # Convenience: fetch messages for summary
    # ----------------------------------------------------------
    async def fetch_messages_for_summary(
        self,
        chat_id: str,
        lookback_hours: int = 24,
        max_messages: int = 100,
    ) -> List[FeishuMessage]:
        """Fetch recent text messages for LLM summarization.

        Auto-paginates until max_messages limit or no more data.
        Filters out non-text messages (images, files, stickers).

        Args:
            chat_id: Chat group ID.
            lookback_hours: Time window in hours.
            max_messages: Max message count (prevents token overflow).

        Returns:
            Text messages sorted by time ascending (oldest first).
        """
        from datetime import timedelta

        end_time = datetime.now()
        start_time = end_time - timedelta(hours=lookback_hours)

        all_msgs: List[FeishuMessage] = []
        page_token: Optional[str] = None

        while len(all_msgs) < max_messages:
            result = await self.list_messages(
                chat_id=chat_id,
                page_size=min(50, max_messages - len(all_msgs)),
                page_token=page_token,
                start_time=start_time,
                end_time=end_time,
            )

            # Keep only messages with readable text
            text_msgs = [
                m for m in result.items
                if m.plain_text and m.plain_text != "[non-text]"
            ]
            all_msgs.extend(text_msgs)

            if not result.has_more or not result.page_token:
                break
            page_token = result.page_token

        # Sort ascending by time (oldest first for LLM context)
        all_msgs.sort(key=lambda m: m.create_time or datetime.min)
        return all_msgs[:max_messages]

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------
    async def close(self) -> None:
        """Close HTTP client connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# ============================================================
# Helpers
# ============================================================

async def _sleep(seconds: float) -> None:
    """Async sleep helper."""
    import asyncio
    await asyncio.sleep(seconds)


def _extract_plain_text(msg_type: str, content: str) -> str:
    """Extract plain text from Feishu message content JSON.

    Feishu message content is a JSON string whose structure depends on msg_type:
      - text:  {"text": "hello"}
      - post:  {"title": "...", "content": [[{"tag":"text","text":"..."}]]}
      - interactive: card with header/elements
      - image/file/audio/media/sticker: no text
    """
    if not content:
        return ""

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return str(content)

    if msg_type == "text":
        return parsed.get("text", "")

    elif msg_type == "post":
        parts: List[str] = []
        title = parsed.get("title", "")
        if title:
            parts.append(title)
        post_content = parsed.get("content", [])
        if isinstance(post_content, list):
            for paragraph in post_content:
                if isinstance(paragraph, list):
                    for elem in paragraph:
                        if isinstance(elem, dict) and elem.get("tag") == "text":
                            parts.append(elem.get("text", ""))
                elif isinstance(paragraph, dict):
                    if paragraph.get("tag") == "text":
                        parts.append(paragraph.get("text", ""))
        return "\n".join(parts)

    elif msg_type == "interactive":
        parts: List[str] = []
        header = parsed.get("header", {})
        header_title = header.get("title", {}).get("content", "")
        if header_title:
            parts.append(header_title)
        for elem in parsed.get("elements", []):
            tag = elem.get("tag", "")
            if tag == "div":
                text_obj = elem.get("text", {})
                if isinstance(text_obj, dict):
                    parts.append(text_obj.get("content", ""))
            elif tag in ("markdown", "plain_text"):
                parts.append(elem.get("content", ""))
        return "\n".join(parts)

    # image / file / audio / media / sticker / system
    return "[non-text]"
