"""InternSU LLM 网关 — 多 Provider 管理、占位符检测、启动探活、故障转移。

【架构定位】
该模块是 Python AI 服务的 LLM 调用统一入口，负责：
1. 封装多个 LLM Provider（DeepSeek、OpenAI）的调用接口
2. 实现 Provider 的静态校验和运行时故障转移
3. 提供 Token 计数和流式输出支持

【核心设计】
- 两阶段初始化：__init__（同步静态校验）+ initialize()（异步探活）
- 选择性重试：仅对 transient 错误重试，401 立即熔断
- Provider 注册顺序：DeepSeek > OpenAI（可配置）

【安全设计】
- 占位符检测：启动时拒绝 sk-your-key-here 等无效 Key
- 401 快速熔断：认证失败立即剔除 Provider，绝不重试
- 运行时监控：Key 被吊销时可检测并切换 Provider
"""

import asyncio
import re
import time
import tiktoken
from typing import AsyncIterator

from app.core.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse, ProviderType
from app.llm.openai_provider import OpenAIProvider
from app.llm.deepseek_provider import DeepSeekProvider
from app.common.exceptions.exceptions import (
    LLMException,
    InvalidConfigException,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


# =========================================================================
# 占位符黑名单 — 不区分大小写正则
# =========================================================================
# 常见的 .env 模板占位符。若 API Key 命中任一模式，静态校验阶段直接拒绝。
# NOTE: 覆盖常见的测试/示例 Key 格式，防止误填
_PLACEHOLDER_PATTERNS = re.compile(
    r'(sk-your-key-here|your-key-here|your-api-key|'
    r'placeholder|changeme|put-your-key|'
    r'^sk-0+$|^sk-a+$|^sk-x+$|^sk-test-)',
    re.IGNORECASE,
)

# OpenAI 标准 Key 前缀（DeepSeek 无固定前缀要求）
_OPENAI_KEY_PREFIX = "sk-"

# 合法 Key 最短长度（防止误填单字符）
_MIN_KEY_LENGTH = 10

# 探活超时（秒）—— 单个 Provider 的 validate_key() 调用时限
_HEALTH_CHECK_TIMEOUT = 5.0


# =========================================================================
# 静态校验工具
# =========================================================================

def _is_placeholder_key(key: str) -> bool:
    """检查 API Key 是否匹配已知占位符模式。

    Args:
        key: 待检查的 API Key
        
    Returns:
        是否为占位符
    """
    if not key or not key.strip():
        return True
    return bool(_PLACEHOLDER_PATTERNS.search(key.strip()))


def _validate_key_format(key: str, provider_name: str) -> tuple[bool, str]:
    """静态校验 Key 格式。

    Args:
        key: 待校验的 API Key
        provider_name: Provider 名称（用于日志）
        
    Returns:
        (is_valid, reason) — is_valid=False 时 reason 为人类可读的失败原因
    """
    stripped = key.strip() if key else ""

    if not stripped:
        return False, f"{provider_name} API Key 未设置（空值）"

    if len(stripped) < _MIN_KEY_LENGTH:
        return False, (
            f"{provider_name} API Key 长度过短（{len(stripped)} 字符），"
            f"有效 Key 至少应 {_MIN_KEY_LENGTH} 字符"
        )

    if _is_placeholder_key(stripped):
        return False, (
            f"{provider_name} API Key 疑似占位符（'{stripped[:20]}...'），"
            f"请填入真实的 API Key"
        )

    if provider_name.lower() == "openai" and not stripped.startswith(_OPENAI_KEY_PREFIX):
        return False, (
            f"OpenAI API Key 应以 '{_OPENAI_KEY_PREFIX}' 开头，"
            f"当前 Key 前缀为 '{stripped[:5]}...'"
        )

    return True, ""


# =========================================================================
# LLMGateway
# =========================================================================

class LLMGateway:
    """企业级 LLM 网关 — 静态校验 + 异步探活 + 选择性重试。

    两阶段初始化:
      1. __init__():  同步静态校验 → 筛选格式合法的 Provider
      2. initialize(): 异步探活     → 每个 Provider 真实 API 调用验证

    【使用方式】
      >>> gateway = LLMGateway()        # 模块加载时（同步，仅格式校验）
      >>> await gateway.initialize()    # FastAPI lifespan 中（异步探活）
    """

    def __init__(self):
        """初始化网关（仅执行静态校验，不发起网络请求）。

        WARNING: 此方法在模块首次导入时执行，若所有 Provider 均无有效配置会抛出异常。
        """
        self._providers: dict[ProviderType, BaseLLMProvider] = {}
        self._tokenizer_cache: dict[str, tiktoken.Encoding] = {}
        self._initialized = False
        self._init_failures: list[str] = []  # 记录静态校验失败的原因
        self._init_providers()

    # ── Phase 1: 静态校验（同步，模块加载时执行）────────────────────

    def _init_providers(self):
        """同步静态校验 — 过滤占位符和格式非法 Key。

        仅做本地规则检查，不发起网络请求。
        通过静态校验的 Provider 进入 _providers 待探活。
        未通过的记录到 _init_failures 供 initialize() 汇总报告。
        """

        # ── DeepSeek ──────────────────────────────────────────────
        is_valid, reason = _validate_key_format(
            settings.deepseek_api_key, "DeepSeek"
        )
        if is_valid:
            self._providers[ProviderType.DEEPSEEK] = DeepSeekProvider()
            logger.debug("DeepSeek Provider: 静态校验通过，等待探活")
        elif settings.deepseek_api_key:
            logger.warning("DeepSeek Provider: 静态校验拒绝 — %s", reason)
            self._init_failures.append(f"DeepSeek: {reason}")

        # ── OpenAI ────────────────────────────────────────────────
        is_valid, reason = _validate_key_format(
            settings.openai_api_key, "OpenAI"
        )
        if is_valid:
            self._providers[ProviderType.OPENAI] = OpenAIProvider()
            logger.debug("OpenAI Provider: 静态校验通过，等待探活")
        elif settings.openai_api_key:
            logger.warning("OpenAI Provider: 静态校验拒绝 — %s", reason)
            self._init_failures.append(f"OpenAI: {reason}")

        # ── 汇总 ─────────────────────────────────────────────────
        if not self._providers:
            failures = "; ".join(self._init_failures) if self._init_failures else "未检测到任何 API Key 配置"
            raise InvalidConfigException(
                message=(
                    "网关未检测到任何有效的大模型服务商配置。"
                    "请检查 .env 中的 DEEPSEEK_API_KEY 和 OPENAI_API_KEY 是否已填入真实值。"
                ),
                detail=failures,
            )

    # ── Phase 2: 异步探活（FastAPI lifespan 中调用）─────────────────

    async def initialize(self):
        """异步启动探活 — 并行验证所有已注册 Provider 的 Key 有效性。

        调用时机: FastAPI lifespan startup 阶段。
        并行执行所有 Provider 的 validate_key()，每个 Provider 限时 {timeout}s。

        【结果处理】
          - 401 (AuthenticationError): 立即剔除，记录 CRITICAL 日志，不重试
          - 超时 (TimeoutError): 保留（视为网络暂时性问题）
          - 其他异常: 保留（视为暂时性故障）

        全部 Provider 探活失败时，抛出 InvalidConfigException。
        """
        if self._initialized:
            return

        provider_names = list(self._providers.keys())
        if not provider_names:
            raise InvalidConfigException(
                message="网关未检测到任何可用的 Provider（静态校验阶段已全部拒绝）"
            )

        logger.info(
            "LLM Gateway 启动探活: %d Provider(s) — %s",
            len(provider_names), ", ".join(p.value for p in provider_names),
        )

        # 并行探活所有 Provider
        tasks = {
            ptype: asyncio.create_task(
                self._validate_provider_key(ptype, provider),
                name=f"health-check-{ptype.value}",
            )
            for ptype, provider in self._providers.items()
        }

        alive_count = 0
        dead_count = 0

        for ptype, task in tasks.items():
            try:
                ok = await task
                if ok:
                    alive_count += 1
                else:
                    dead_count += 1
            except asyncio.CancelledError:
                logger.warning("Provider %s 探活被取消", ptype.value)
                dead_count += 1
            except Exception:
                logger.warning("Provider %s 探活异常", ptype.value, exc_info=True)
                dead_count += 1

        self._initialized = True
        logger.info(
            "LLM Gateway 探活完成: %d 存活, %d 剔除",
            alive_count, dead_count,
        )

        if not self._providers:
            raise InvalidConfigException(
                message=(
                    "网关未检测到任何有效的大模型服务商配置。"
                    "所有已注册 Provider 的 API Key 均已探活失败（401 或超时）。"
                    "请检查 .env 中的 API Key 是否有效。"
                ),
                detail="; ".join(
                    f"{ptype.value}: {reason}"
                    for ptype, reason in self._init_failures
                ) if self._init_failures else "全部 Provider 探活失败",
            )

    async def _validate_provider_key(
        self, ptype: ProviderType, provider: BaseLLMProvider,
    ) -> bool:
        """对单个 Provider 执行探活。

        Args:
            ptype: Provider 类型
            provider: Provider 实例
            
        Returns:
            True  — 探活通过，Provider 保留
            False — 探活失败（401），Provider 已从 _providers 中移除
        """
        name = ptype.value
        try:
            await asyncio.wait_for(
                provider.validate_key(),
                timeout=_HEALTH_CHECK_TIMEOUT,
            )
            logger.info("Provider %s 探活通过 ✓", name)
            return True

        except asyncio.TimeoutError:
            # 超时不剔除，视为暂时性网络问题
            logger.warning(
                "Provider %s 探活超时 (%ss) — 保留（可能为网络延迟）",
                name, _HEALTH_CHECK_TIMEOUT,
            )
            return True

        except Exception as e:
            # 检测是否为 401 认证错误
            if self._is_auth_error(e):
                logger.critical(
                    "Provider %s 认证失败 (401) — 永久剔除！"
                    " 请检查 .env 中的 %s_API_KEY 是否有效。"
                    " 错误详情: %s",
                    name,
                    name.upper(),
                    e,
                )
                del self._providers[ptype]
                self._init_failures.append(
                    f"{name}: 401 Unauthorized — API Key 无效"
                )
                return False
            else:
                logger.warning(
                    "Provider %s 探活异常 (%s: %s) — 保留（视为暂时性故障）",
                    name, type(e).__name__, e,
                )
                return True

    @staticmethod
    def _is_auth_error(exception: Exception) -> bool:
        """判断异常是否为 401 认证失败。

        openai 包在不同版本中 AuthenticationError 的路径可能不同。
        此处通过类名匹配和状态码双重校验实现版本兼容。
        
        Args:
            exception: 待检查的异常对象
            
        Returns:
            是否为 401 认证错误
        """
        exc_type = type(exception).__name__
        exc_module = type(exception).__module__

        # 直接匹配类名
        if exc_type == "AuthenticationError":
            return True

        # 状态码匹配（openai < 1.0 兼容）
        status = getattr(exception, "status_code", None)
        if status == 401:
            return True

        # 状态码匹配（openai >= 1.0 兼容）
        http_status = getattr(exception, "status", None)
        if http_status == 401:
            return True

        # 递归检查 __cause__ 链（异常可能被包装）
        cause = exception.__cause__
        if cause is not None:
            return LLMGateway._is_auth_error(cause)

        return False

    # ── Provider 管理 ──────────────────────────────────────────────

    def register(self, provider: BaseLLMProvider):
        """手动注册 Provider（覆盖自动配置）。
        
        Args:
            provider: Provider 实例
        """
        self._providers[provider.provider_type] = provider
        logger.info("手动注册 Provider: %s", provider.provider_type.value)

    def _select_provider(self, model: str | None = None) -> BaseLLMProvider:
        """选择 Provider（按 model 名匹配 > default_provider 偏好 > 任意可用）。

        【选择优先级】
        1. 按 model 名精确匹配（如 deepseek-chat → DeepSeek）
        2. 按 settings.default_provider 配置
        3. 兜底任意可用 Provider
        
        Args:
            model: 模型名称（可选）
            
        Returns:
            选中的 Provider 实例
            
        Raises:
            InvalidConfigException: 无可用 Provider
        """
        if not self._providers:
            raise InvalidConfigException(
                message=(
                    "网关未检测到任何有效的大模型服务商配置。"
                    "请检查 .env 中的 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 是否有效。"
                )
            )

        # 按 model 名匹配
        if model:
            for p in self._providers.values():
                prefix = p.default_model.split("-")[0]
                if model.startswith(prefix):
                    return p

        # 按 settings 默认偏好
        try:
            preferred = ProviderType(settings.default_provider)
            if preferred in self._providers:
                return self._providers[preferred]
        except ValueError:
            pass

        # 兜底: 任意可用 Provider
        return next(iter(self._providers.values()))

    # ── Token 计数 ────────────────────────────────────────────────

    def _get_tokenizer(self, model: str) -> tiktoken.Encoding:
        """获取模型对应的 Tokenizer（带缓存）。
        
        Args:
            model: 模型名称
            
        Returns:
            tiktoken Encoding 实例
        """
        if model not in self._tokenizer_cache:
            try:
                self._tokenizer_cache[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # 未知模型使用 cl100k_base（GPT-4/ChatGPT 使用的编码器）
                self._tokenizer_cache[model] = tiktoken.get_encoding("cl100k_base")
        return self._tokenizer_cache[model]

    def count_tokens(self, messages: list[dict], model: str) -> int:
        """计算消息列表的 Token 数量。

        使用 tiktoken 精确计数，用于：
        1. 估算 API 调用成本
        2. 控制上下文长度防止超过 max_tokens 限制
        
        Args:
            messages: 消息列表 [{role, content}, ...]
            model: 模型名称
            
        Returns:
            Token 估算数量
        """
        enc = self._get_tokenizer(model)
        count = 0
        for msg in messages:
            count += 4  # message framing (role + content overhead)
            for key in ("content", "role"):
                val = msg.get(key, "")
                if isinstance(val, str):
                    count += len(enc.encode(val))
        count += 2  # reply priming
        return count

    # ── 核心 API ──────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """非流式聊天 — Provider 选择 + 调用。

        【参数说明】
        - messages: 对话消息列表，格式 [{role: "user"/"assistant"/"system", content: str}]
        - model: 模型名称（可选，不填则按 default_provider 选择）
        - temperature: 温度参数 [0, 2]，越低越确定性（推荐 0.1-0.3 用于 RAG）
        - max_tokens: 最大生成 Token 数
        
        Returns:
            LLMResponse: 包含 content（回答文本）、usage（Token 消耗）等字段
            
        Raises:
            LLMException: LLM 调用失败
            InvalidConfigException: 无可用 Provider
        """
        provider = self._select_provider(model)
        start = time.time()
        try:
            result = await provider.chat(
                messages, model=model,
                temperature=temperature, max_tokens=max_tokens, **kwargs,
            )
            elapsed = int((time.time() - start) * 1000)
            logger.debug("chat: provider=%s model=%s elapsed=%dms",
                         provider.provider_type.value, result.model, elapsed)
            return result
        except Exception as e:
            if self._is_auth_error(e):
                # 运行时 401: Provider 在探活后失效（如 Key 被吊销）
                logger.critical(
                    "运行时认证失败: provider=%s — 立即从活跃池移除",
                    provider.provider_type.value,
                )
                del self._providers[provider.provider_type]
                # 尝试使用其他 Provider（不递归，防止栈溢出）
                if self._providers:
                    logger.warning("尝试故障转移到其他 Provider")
                    return await self.chat(messages, model=None, **kwargs)
            raise LLMException(f"LLM call failed: {e}")

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式聊天 — 逐 token 异步生成器。

        【使用场景】
        用于 SSE 实时推送，用户可看到逐字生成的回答。

        WARNING: 流式调用不做自动重试，因为 token 已部分发送无法回退。
        调用方应在流断开时自行决定是否重试。
        
        Args:
            messages: 对话消息列表
            model: 模型名称
            temperature: 温度参数
            
        Yields:
            逐字生成的回答片段
        """
        provider = self._select_provider(model)
        try:
            async for token in provider.chat_stream(
                messages, model=model, temperature=temperature, **kwargs,
            ):
                yield token
        except Exception as e:
            if self._is_auth_error(e):
                logger.critical(
                    "流式认证失败: provider=%s",
                    provider.provider_type.value,
                )
                del self._providers[provider.provider_type]
            raise LLMException(f"Stream failed: {e}")

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """文本向量化。

        Args:
            texts: 待向量化的文本列表
            model: 模型名称
            
        Returns:
            向量列表，每个向量维度为 1024（BGE-M3）
        """
        provider = self._select_provider()
        start = time.time()
        result = await provider.embed(texts, model=model)
        elapsed = (time.time() - start) * 1000
        logger.debug("Embedding %d texts in %.0fms", len(texts), elapsed)
        return result

    # ── 状态查询 ──────────────────────────────────────────────────

    @property
    def available_providers(self) -> list[str]:
        """获取当前可用的 Provider 列表。"""
        return [p.value for p in self._providers]

    @property
    def is_initialized(self) -> bool:
        """网关是否已完成探活初始化。"""
        return self._initialized

    @property
    def init_diagnostics(self) -> dict:
        """返回初始化诊断信息（供 health API 使用）。"""
        return {
            "initialized": self._initialized,
            "providers": self.available_providers,
            "failures": self._init_failures,
        }


# ── 模块级单例 ─────────────────────────────────────────────────────────
# 注意: __init__ 仅在模块首次导入时执行一次（同步静态校验）。
# 异步探活需在 FastAPI lifespan 中显式调用 await llm_gateway.initialize()

llm_gateway = LLMGateway()
