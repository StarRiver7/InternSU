from typing import AsyncIterator
from openai import AsyncOpenAI, AuthenticationError
from app.core.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse, ProviderType

_OPENAI_AUTH_ERROR_MSG = (
    "OpenAI API Key 无效 —— 请检查 OPENAI_API_KEY 是否为占位符 "
    "（如 sk-your-key-here）。有效 Key 以 sk- 开头且长度 > 20 字符。"
)


class OpenAIProvider(BaseLLMProvider):
    _default_embedding_model: str = "text-embedding-3-small"
    """OpenAI 提供者 - GPT-4o, GPT-4o-mini, text-embedding-3-small"""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._default_model = settings.openai_default_model

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    @property
    def default_model(self) -> str:
        return self._default_model

    async def chat(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096, **kwargs,
    ) -> LLMResponse:
        model = model or self._default_model
        resp = await self._client.chat.completions.create(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens, **kwargs,
        )
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=resp.model,
            provider=ProviderType.OPENAI,
            usage=resp.usage.model_dump() if resp.usage else None,
            finish_reason=choice.finish_reason,
        )

    async def chat_stream(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, **kwargs,
    ) -> AsyncIterator[str]:
        model = model or self._default_model
        stream = await self._client.chat.completions.create(
            model=model, messages=messages,
            temperature=temperature, stream=True, **kwargs,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model = model or self._default_embedding_model
        resp = await self._client.embeddings.create(model=model, input=texts)
        return [d.embedding for d in resp.data]

    # ── 启动探活 ──────────────────────────────────────────────────────

    async def validate_key(self) -> bool:
        """使用 /v1/models 端点验证 API Key（零 Token 消耗）。

        OpenAI 的 models.list() 是最便宜的验证方式 ——
        不需要消耗 Token，仅认证 API Key。
        """
        try:
            await self._client.models.list()
            return True
        except AuthenticationError:
            raise
        except Exception:
            # 网络超时、服务不可达等暂时性故障 —— 给予信任，保留 Provider
            return True

