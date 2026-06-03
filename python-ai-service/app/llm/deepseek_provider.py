from typing import AsyncIterator
from openai import AsyncOpenAI, AuthenticationError
from app.core.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse, ProviderType

_DEEPSEEK_AUTH_ERROR_MSG = (
    "DeepSeek API Key 无效 —— 请检查 DEEPSEEK_API_KEY 是否正确。"
    "DeepSeek Key 可从 https://platform.deepseek.com/api_keys 获取。"
)


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek 提供者 - deepseek-chat (V3), deepseek-reasoner (R1)"""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self._default_model = settings.deepseek_default_model

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.DEEPSEEK

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
            provider=ProviderType.DEEPSEEK,
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
        raise NotImplementedError("DeepSeek does not provide embedding API")

    # ── 启动探活 ──────────────────────────────────────────────────────

    async def validate_key(self) -> bool:
        """验证 DeepSeek API Key 有效性。

        策略: 先尝试 models.list()（零 Token），
        若 DeepSeek 不支持该端点则回退到最小化 chat completion（max_tokens=1）。
        """
        try:
            # 首选: models.list() — 零 Token，最快
            await self._client.models.list()
            return True
        except AuthenticationError:
            raise
        except Exception:
            pass  # 可能是不支持 models 端点，回退到 chat

        # 回退: 最小化 completion，单 token
        try:
            await self._client.chat.completions.create(
                model=self._default_model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return True
        except AuthenticationError:
            raise
        except Exception:
            # 其他异常视为暂时性故障，给予信任
            return True
