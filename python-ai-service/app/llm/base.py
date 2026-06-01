from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional
from enum import Enum


class ProviderType(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


@dataclass
class ModelConfig:
    provider: ProviderType
    model_name: str
    api_key: str
    base_url: str
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 0
    rate_limit_rpm: int = 60
    extra: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: ProviderType
    usage: dict | None = None
    finish_reason: str | None = None


class BaseLLMProvider(ABC):

    @abstractmethod
    async def chat(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096, **kwargs,
    ) -> LLMResponse:
        pass

    @abstractmethod
    async def chat_stream(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, **kwargs,
    ) -> AsyncIterator[str]:
        pass

    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        pass

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        pass

    # ── 启动探活（v2） ──────────────────────────────────────────────────

    async def validate_key(self) -> bool:
        """验证 API Key 有效性 —— 尽可能低成本的异步探活。

        由 LLMGateway.initialize() 在服务启动时调用。
        具体 Provider 应覆写此方法，使用最省 Token 的方式验证 API Key。

        约定:
          - 返回 True:  Key 有效（或无法确定，给予信任）
          - 抛出 openai.AuthenticationError: Key 确定无效（401），网关将其剔除
          - 抛出其他异常: 视为暂时性故障，网关保留该 Provider

        默认实现: 不执行任何操作，返回 True（无验证 = 给予信任）。
        """
        return True
