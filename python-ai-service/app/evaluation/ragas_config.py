"""Ragas LLM 配置 — 将 InternSU LLM Gateway 适配为 Ragas 风格的评估接口。

由于 ragas 库与项目的 langchain 版本存在依赖冲突，
本模块直接使用 InternSU LLM Gateway 实现 Ragas 核心指标的评分逻辑。

使用方式:
    from app.evaluation.ragas_config import evaluate_with_llm
    score = await evaluate_with_llm(prompt="评估以下内容...")
"""

import asyncio
import json
import re
from typing import Optional

from app.llm.gateway import llm_gateway
from app.pipeline.embedder import embedding_engine
from app.core.logger import get_logger

logger = get_logger(__name__)


async def evaluate_with_llm(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
    max_tokens: int = 1024,
    model: str = "deepseek-chat",
) -> str:
    """使用 LLM Gateway 执行评估提示。

    Args:
        prompt: 评估提示文本
        system_prompt: 系统提示（可选）
        temperature: 温度参数（低温度保证评分稳定性）
        max_tokens: 最大输出 token 数
        model: 使用的模型名称

    Returns:
        LLM 返回的评估结果文本
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = await llm_gateway.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content.strip()
    except Exception as e:
        logger.error(f"LLM 评估调用失败: {e}")
        return ""


async def evaluate_with_llm_json(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
    model: str = "deepseek-chat",
) -> dict:
    """使用 LLM 执行评估并解析 JSON 结果。

    Args:
        prompt: 评估提示（要求 LLM 返回 JSON）
        system_prompt: 系统提示
        temperature: 温度参数
        model: 使用的模型

    Returns:
        解析后的 JSON 字典
    """
    result = await evaluate_with_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        model=model,
    )

    if not result:
        return {}

    # 尝试从文本中提取 JSON
    try:
        # 尝试直接解析
        return json.loads(result)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', result, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找到第一个 { 到最后一个 } 之间的内容
    start = result.find('{')
    end = result.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(result[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning(f"无法解析 LLM 返回的 JSON: {result[:200]}")
    return {}


async def compute_embedding_similarity(text1: str, text2: str) -> float:
    """计算两段文本的余弦相似度（使用 BGE-M3 Embedding）。

    Args:
        text1: 文本 1
        text2: 文本 2

    Returns:
        余弦相似度分数 [0, 1]
    """
    try:
        vec1 = await embedding_engine.embed_query(text1)
        vec2 = await embedding_engine.embed_query(text2)

        # 余弦相似度
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return max(0.0, min(1.0, similarity))
    except Exception as e:
        logger.error(f"Embedding 相似度计算失败: {e}")
        return 0.0
