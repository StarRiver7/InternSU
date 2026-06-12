"""
飞书客户端 — 飞书开放 API 客户端。

封装飞书开放平台 API 调用:
  - 租户访问令牌管理 (自动刷新)
  - 列出聊天
  - 列出消息 (分页和时间范围)
  - 消息内容解析
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
# 数据模型
# ============================================================

@dataclass
class FeishuMessage:
    """解析后的飞书消息实体。"""
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
    """聊天群基本信息。"""
    chat_id: str
    name: str = ""
    description: str = ""
    member_count: int = 0


@dataclass
class PaginatedResult:
    """统一分页结果。"""
    items: List[Any] = field(default_factory=list)
    total: int = 0
    has_more: bool = False
    page_token: str = ""


@dataclass
class TokenCache:
    """带 TTL 的内存访问令牌缓存。"""
    token: str = ""
    expires_at: float = 0.0

    @property
    def is_valid(self) -> bool:
        return bool(self.token) and time.time() < self.expires_at


# ============================================================
# 飞书客户端
# ============================================================

class FeishuClient:
    """飞书开放平台异步 HTTP 客户端。

    处理令牌生命周期、分页、重试和错误日志。

    用法:
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
        """初始化飞书客户端。

        参数:
            app_id: 飞书应用 ID (来自开放平台)。
            app_secret: 飞书应用密钥。
            base_url: API 基础 URL (国际版使用 open.larksuite.com)。
            token_cache_ttl: 令牌缓存 TTL (秒，默认 110 分钟)。
            default_page_size: 列表 API 的默认页面大小。
            max_retries: 失败时的最大重试次数。
            request_timeout: HTTP 请求超时 (秒)。
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
    # HTTP 客户端 (异步上下文延迟初始化)
    # ----------------------------------------------------------
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx AsyncClient (连接池复用)。"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._request_timeout),
            )
        return self._client

    # ----------------------------------------------------------
    # 令牌管理
    # ----------------------------------------------------------
    async def _fetch_access_token(self) -> str:
        """调用飞书租户访问令牌 API，缓存结果。

        返回:
            访问令牌字符串。

        异常:
            RuntimeError: 如果令牌获取在所有重试后失败。
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
                # 提前 10 分钟过期作为安全边际
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
                # 指数退避: 2s, 4s, 8s...
                await _sleep(2 ** attempt)

        raise RuntimeError("Feishu token fetch aborted unexpectedly")

    async def _ensure_token(self) -> str:
        """如果缓存的令牌有效则返回，否则获取新令牌。"""
        if self._token_cache.is_valid:
            return self._token_cache.token
        return await self._fetch_access_token()

    # ----------------------------------------------------------
    # 底层 HTTP 请求
    # ----------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Dict:
        """统一的 HTTP 请求，包含认证、重试和错误处理。

        参数:
            method: HTTP 方法 (GET/POST)。
            path: API 路径 (例如 /open-apis/im/v1/chats)。
            params: URL 查询参数。
            json_body: JSON 请求体。

        返回:
            API 响应数据字典 (从飞书标准信封中提取)。
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
                    # 令牌过期错误码: 刷新并重试一次
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
    # 聊天列表
    # ----------------------------------------------------------
    async def list_chats(
        self,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> PaginatedResult:
        """列出机器人所属的聊天。

        参数:
            page_size: 每页条目数 (默认来自配置)。
            page_token: 下一页的分页令牌。
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
    # 消息列表
    # ----------------------------------------------------------
    async def list_messages(
        self,
        chat_id: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> PaginatedResult:
        """列出聊天中的消息。

        参数:
            chat_id: 聊天群 ID。
            page_size: 每页条目数。
            page_token: 分页令牌。
            start_time: 最早消息时间 (包含)。
            end_time: 最晚消息时间 (包含)。
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
    # 消息解析
    # ----------------------------------------------------------
    def _parse_message(self, raw: Dict, default_chat_id: str) -> FeishuMessage:
        """将原始飞书消息 JSON 解析为 FeishuMessage 实体。

        根据 msg_type 提取纯文本:
          - text: 直接文本字段
          - post: 遍历内容块，连接文本元素
          - interactive: 提取卡片文本字段
          - 其他: 标记为 [non-text]
        """
        msg_type = raw.get("msg_type", "text")
        body = raw.get("body", {})
        content = body.get("content", "")

        # 提取纯文本
        plain_text = _extract_plain_text(msg_type, content)

        # 提取提及
        mentions: List[str] = []
        for m in raw.get("mentions", []):
            mid = m.get("id", "")
            if isinstance(mid, dict):
                uid = mid.get("union_id") or mid.get("open_id", "")
            else:
                uid = str(mid) if mid else ""
            if uid:
                mentions.append(uid)
        # 解析创建时间 (毫秒时间戳)
        create_time = None
        raw_time = raw.get("create_time", "")
        if raw_time:
            try:
                create_time = datetime.fromtimestamp(int(raw_time) / 1000)
            except (ValueError, TypeError, OSError):
                logger.warning("Failed to parse create_time: %s", raw_time)

        msg = FeishuMessage(
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

        logger.debug(
            "Parsed message: id=%s, type=%s, sender=%s, "
            "create_time=%s, plain_text_len=%d",
            msg.message_id, msg_type, msg.sender_name,
            create_time.isoformat() if create_time else "None",
            len(plain_text),
        )

        return msg

    # ----------------------------------------------------------
    # 便捷方法: 获取摘要消息
    # ----------------------------------------------------------
    async def fetch_messages_for_summary(
        self,
        chat_id: str,
        lookback_hours: int = 24,
        max_messages: int = 100,
    ) -> List[FeishuMessage]:
        """获取最近的文本消息用于 LLM 摘要。

        自动分页直到达到 max_messages 限制或没有更多数据。
        过滤掉非文本消息 (图片、文件、表情包)。

        参数:
            chat_id: 聊天群 ID。
            lookback_hours: 时间窗口 (小时)。
            max_messages: 最大消息数量 (防止令牌溢出)。

        返回:
            按时间升序排序的文本消息 (最旧的在前)。
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        logger.info(
            "fetch_messages_for_summary: chat_id=%s, lookback_hours=%d, "
            "cutoff_time=%s, now=%s",
            chat_id, lookback_hours, cutoff_time.isoformat(),
            datetime.now().isoformat(),
        )

        all_msgs: List[FeishuMessage] = []
        page_token: Optional[str] = None
        page_count = 0
        raw_count = 0
        filtered_out_count = 0
        old_count = 0

        while len(all_msgs) < max_messages:
            page_count += 1
            result = await self.list_messages(
                chat_id=chat_id,
                page_size=min(50, max_messages - len(all_msgs)),
                page_token=page_token,
            )
            logger.info(
                "Page %d: got %d messages, has_more=%s",
                page_count, len(result.items), result.has_more,
            )

            for m in result.items:
                raw_count += 1
                ct = m.create_time
                # 飞书 API 按时间升序返回（最旧在前）。
                # 遇到早于截止时间的消息直接跳过（还在历史区域）；
                # 一旦遇到时效内的消息，后续全部都是时效内的。
                if ct and ct < cutoff_time:
                    old_count += 1
                    continue
                # 只保留有可读文本的消息
                if m.plain_text and m.plain_text != "[non-text]":
                    all_msgs.append(m)
                else:
                    filtered_out_count += 1

            if not result.has_more or not result.page_token:
                break
            page_token = result.page_token

        logger.info(
            "fetch_messages_for_summary result: collected=%d, raw=%d, "
            "old_skipped=%d, filtered_out=%d, pages=%d",
            len(all_msgs), raw_count, old_count, filtered_out_count, page_count,
        )

        # 按时间升序排序 (最旧的在前，用于 LLM 上下文)
        all_msgs.sort(key=lambda m: m.create_time or datetime.min)
        return all_msgs[:max_messages]

    # ----------------------------------------------------------
    # 清理
    # ----------------------------------------------------------
    async def close(self) -> None:
        """关闭 HTTP 客户端连接池。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# ============================================================
# 辅助函数
# ============================================================

async def _sleep(seconds: float) -> None:
    """异步睡眠辅助函数。"""
    import asyncio
    await asyncio.sleep(seconds)


def _extract_plain_text(msg_type: str, content: str) -> str:
    """从飞书消息内容 JSON 中提取纯文本。

    飞书消息内容是一个 JSON 字符串，其结构取决于 msg_type:
      - text:  {"text": "hello"}
      - post:  {"title": "...", "content": [[{"tag":"text","text":"..."}]]}
      - interactive: 带有 header/elements 的卡片
      - image/file/audio/media/sticker: 无文本
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
