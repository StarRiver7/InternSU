"""Ragas LLM 配置适配层 —— 将 InternSU LLM Gateway 封装为 Ragas 风格的评估接口。

【架构定位】
该模块是 Ragas 评估框架与 InternSU LLM Gateway 之间的适配层。
由于 ragas 库与项目的 langchain 版本存在依赖冲突（ragas 0.4.3 要求
langchain-core 0.3.x，而 langgraph 1.2.1 要求 langchain-core >= 1.4.0），
本模块直接使用 InternSU LLM Gateway 实现 Ragas 核心指标的评分逻辑。

【设计思路】
Ragas 的 Faithfulness/Answer Relevancy 等指标需要调用 LLM 进行评判（LLM-as-Judge），
本模块封装了三个核心函数：
  1. evaluate_with_llm(): 通用 LLM 评估调用
  2. evaluate_with_llm_json(): LLM 评估 + JSON 结果解析
  3. compute_embedding_similarity(): 基于 BGE-M3 的文本相似度计算

【使用方式】
    from app.evaluation.ragas_config import evaluate_with_llm
    score_text = await evaluate_with_llm(prompt="评估以下内容...")
"""

import json
import re

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
    """使用 LLM Gateway 执行评估提示，返回原始文本结果。

    通过项目的 LLM Gateway 调用 DeepSeek V3 进行 LLM-as-Judge 评分。
    低温度参数（temperature=0.1）保证评分的稳定性和可重复性。

    Args:
        prompt: 评估提示文本（包含评估标准和待评估内容）
        system_prompt: 系统提示（可选，用于设定 LLM 角色）
        temperature: 温度参数，低值保证评分稳定性
        max_tokens: 最大输出 token 数
        model: 使用的 LLM 模型名称

    Returns:
        LLM 返回的评估结果文本（通常是 0-1 的数字分数）

    Raises:
        LLMException: LLM 调用失败时返回空字符串
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

    在 evaluate_with_llm 的基础上增加 JSON 解析逻辑，
    支持从纯 JSON、markdown 代码块、以及混合文本中提取 JSON。

    Args:
        prompt: 评估提示（要求 LLM 返回 JSON 格式）
        system_prompt: 系统提示
        temperature: 温度参数
        model: 使用的 LLM 模型

    Returns:
        解析后的 JSON 字典，解析失败时返回空字典
    """
    result = await evaluate_with_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        model=model,
    )

    if not result:
        return {}

    # 三级 JSON 提取策略：直接解析 → markdown 代码块 → 文本截取
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', result, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

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
    """计算两段文本的余弦相似度（基于 BGE-M3 Embedding）。

    将两段文本分别通过 BGE-M3 模型编码为 1024 维稠密向量，
    然后计算余弦相似度作为语义相似性度量。

    Args:
        text1: 文本 1
        text2: 文本 2

    Returns:
        余弦相似度分数 [0, 1]，1 表示完全相同，0 表示完全不同
    """
    try:
        vec1 = await embedding_engine.embed_query(text1)
        vec2 = await embedding_engine.embed_query(text2)

        # 余弦相似度: cos(A, B) = (A·B) / (|A| × |B|)
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
