"""Ragas 核心指标自定义实现 — 基于 LLM Judge 的 RAG 评估指标。

指标说明:
1. Faithfulness (忠实度): 回答是否基于检索上下文，有无幻觉
2. Answer Relevancy (回答相关性): 回答是否真正回答了用户的问题
3. Context Precision (上下文精确率): 检索结果中相关文档的比例
4. Context Recall (上下文召回率): 检索是否覆盖了所有必要信息
5. Answer Correctness (回答正确性): 与标准答案的一致程度

每个指标通过 LLM 进行评判，返回 0-1 的分数。
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from app.evaluation.ragas_config import evaluate_with_llm, evaluate_with_llm_json
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── 指标评分 Prompt 模板 ──────────────────────────────────────────

FAITHFULNESS_PROMPT = """你是一个严格的事实核查专家。请评估以下回答是否忠实于给定的上下文。

## 上下文（检索到的文档片段）
{contexts}

## 待评估的回答
{answer}

## 评估标准
- 1.0 分: 回答中的所有声明都可以在上下文中找到依据，没有编造内容
- 0.8 分: 回答中绝大部分声明有上下文依据，仅有极少量推断
- 0.6 分: 回答中部分声明有上下文依据，但也有一些推断或简化
- 0.4 分: 回答中有较多内容无法在上下文中找到依据
- 0.2 分: 回答大部分是编造的，仅有少量与上下文相关
- 0.0 分: 回答完全是编造的，与上下文无关

请只返回一个 0-1 之间的数字分数，不要解释。"""

ANSWER_RELEVANCY_PROMPT = """你是一个回答质量评估专家。请评估以下回答是否真正回答了用户的问题。

## 用户问题
{question}

## 待评估的回答
{answer}

## 评估标准
- 1.0 分: 回答完全回答了用户的问题，内容准确且切题
- 0.8 分: 回答基本回答了问题，但有少量无关内容
- 0.6 分: 回答部分回答了问题，但遗漏了一些关键信息
- 0.4 分: 回答与问题相关，但没有实质性回答
- 0.2 分: 回答与问题关联度很低
- 0.0 分: 回答完全答非所问

请只返回一个 0-1 之间的数字分数，不要解释。"""

CONTEXT_PRECISION_PROMPT = """你是一个检索质量评估专家。请评估以下检索结果中相关文档的比例。

## 用户问题
{question}

## 检索到的文档片段
{contexts}

## 评估标准
- 1.0 分: 所有检索到的文档都与问题高度相关
- 0.8 分: 大部分文档与问题相关，仅有少量不相关
- 0.6 分: 约一半文档与问题相关
- 0.4 分: 少量文档与问题相关，大部分不相关
- 0.2 分: 仅有极少量文档与问题相关
- 0.0 分: 所有文档都与问题无关

请只返回一个 0-1 之间的数字分数，不要解释。"""

CONTEXT_RECALL_PROMPT = """你是一个信息覆盖度评估专家。请评估检索到的文档是否覆盖了回答问题所需的所有信息。

## 用户问题
{question}

## 标准答案
{ground_truth}

## 检索到的文档片段
{contexts}

## 评估标准
- 1.0 分: 检索到的文档覆盖了标准答案中的所有关键信息点
- 0.8 分: 检索到的文档覆盖了大部分关键信息点
- 0.6 分: 检索到的文档覆盖了约一半的关键信息点
- 0.4 分: 检索到的文档仅覆盖了少量关键信息点
- 0.2 分: 检索到的文档几乎没有覆盖关键信息点
- 0.0 分: 检索到的文档完全不包含关键信息

请只返回一个 0-1 之间的数字分数，不要解释。"""

ANSWER_CORRECTNESS_PROMPT = """你是一个答案正确性评估专家。请评估以下回答与标准答案的一致程度。

## 用户问题
{question}

## 待评估的回答
{answer}

## 标准答案
{ground_truth}

## 评估标准
- 1.0 分: 回答与标准答案完全一致，信息准确无误
- 0.8 分: 回答与标准答案基本一致，仅有极少量差异
- 0.6 分: 回答与标准答案部分一致，有一些遗漏或简化
- 0.4 分: 回答与标准答案有较大差异
- 0.2 分: 回答与标准答案几乎不一致
- 0.0 分: 回答与标准答案完全不一致

请只返回一个 0-1 之间的数字分数，不要解释。"""


@dataclass
class MetricResult:
    """单个指标的评估结果。"""

    name: str
    score: float
    details: str = ""


@dataclass
class SampleEvaluation:
    """单条样本的完整评估结果。"""

    query: str
    answer: str
    metrics: list[MetricResult] = field(default_factory=list)

    @property
    def scores(self) -> dict[str, float]:
        return {m.name: m.score for m in self.metrics}

    @property
    def average_score(self) -> float:
        if not self.metrics:
            return 0.0
        return sum(m.score for m in self.metrics) / len(self.metrics)


@dataclass
class EvaluationResult:
    """批量评估的完整结果。"""

    samples: list[SampleEvaluation] = field(default_factory=list)

    @property
    def metric_names(self) -> list[str]:
        if not self.samples:
            return []
        return list(self.samples[0].scores.keys())

    @property
    def average_scores(self) -> dict[str, float]:
        """各指标的平均分。"""
        if not self.samples:
            return {}
        names = self.metric_names
        return {
            name: sum(s.scores.get(name, 0) for s in self.samples) / len(self.samples)
            for name in names
        }

    @property
    def overall_average(self) -> float:
        """所有指标的总平均分。"""
        avgs = self.average_scores
        if not avgs:
            return 0.0
        return sum(avgs.values()) / len(avgs)


def _parse_score(text: str) -> float:
    """从 LLM 返回的文本中解析分数。"""
    text = text.strip()

    # 尝试直接解析为浮点数
    try:
        score = float(text)
        return max(0.0, min(1.0, score))
    except ValueError:
        pass

    # 尝试从文本中提取数字
    import re
    numbers = re.findall(r'0?\.\d+|1\.0|0', text)
    if numbers:
        try:
            score = float(numbers[0])
            return max(0.0, min(1.0, score))
        except ValueError:
            pass

    logger.warning(f"无法解析分数: {text[:100]}")
    return 0.0


async def evaluate_faithfulness(
    question: str,
    answer: str,
    contexts: list[str],
    model: str = "deepseek-chat",
) -> MetricResult:
    """评估回答忠实度（Faithfulness）。

    检查回答是否基于检索到的上下文，有无幻觉。

    Args:
        question: 用户问题
        answer: LLM 生成的回答
        contexts: 检索到的文档片段列表
        model: 使用的 LLM 模型

    Returns:
        MetricResult 包含分数和详情
    """
    contexts_text = "\n\n".join(f"[片段{i+1}] {c}" for i, c in enumerate(contexts))
    prompt = FAITHFULNESS_PROMPT.format(contexts=contexts_text, answer=answer)

    result = await evaluate_with_llm(prompt, model=model)
    score = _parse_score(result)

    return MetricResult(
        name="faithfulness",
        score=score,
        details=result[:200] if result else "评估失败",
    )


async def evaluate_answer_relevancy(
    question: str,
    answer: str,
    model: str = "deepseek-chat",
) -> MetricResult:
    """评估回答相关性（Answer Relevancy）。

    检查回答是否真正回答了用户的问题。

    Args:
        question: 用户问题
        answer: LLM 生成的回答
        model: 使用的 LLM 模型

    Returns:
        MetricResult 包含分数和详情
    """
    prompt = ANSWER_RELEVANCY_PROMPT.format(question=question, answer=answer)
    result = await evaluate_with_llm(prompt, model=model)
    score = _parse_score(result)

    return MetricResult(
        name="answer_relevancy",
        score=score,
        details=result[:200] if result else "评估失败",
    )


async def evaluate_context_precision(
    question: str,
    contexts: list[str],
    model: str = "deepseek-chat",
) -> MetricResult:
    """评估上下文精确率（Context Precision）。

    检查检索到的上下文中，有多少是与问题相关的。

    Args:
        question: 用户问题
        contexts: 检索到的文档片段列表
        model: 使用的 LLM 模型

    Returns:
        MetricResult 包含分数和详情
    """
    contexts_text = "\n\n".join(f"[片段{i+1}] {c}" for i, c in enumerate(contexts))
    prompt = CONTEXT_PRECISION_PROMPT.format(question=question, contexts=contexts_text)
    result = await evaluate_with_llm(prompt, model=model)
    score = _parse_score(result)

    return MetricResult(
        name="context_precision",
        score=score,
        details=result[:200] if result else "评估失败",
    )


async def evaluate_context_recall(
    question: str,
    ground_truth: str,
    contexts: list[str],
    model: str = "deepseek-chat",
) -> MetricResult:
    """评估上下文召回率（Context Recall）。

    检查检索是否覆盖了回答问题所需的所有信息。
    需要 ground_truth 才能计算。

    Args:
        question: 用户问题
        ground_truth: 标准答案
        contexts: 检索到的文档片段列表
        model: 使用的 LLM 模型

    Returns:
        MetricResult 包含分数和详情
    """
    contexts_text = "\n\n".join(f"[片段{i+1}] {c}" for i, c in enumerate(contexts))
    prompt = CONTEXT_RECALL_PROMPT.format(
        question=question,
        ground_truth=ground_truth,
        contexts=contexts_text,
    )
    result = await evaluate_with_llm(prompt, model=model)
    score = _parse_score(result)

    return MetricResult(
        name="context_recall",
        score=score,
        details=result[:200] if result else "评估失败",
    )


async def evaluate_answer_correctness(
    question: str,
    answer: str,
    ground_truth: str,
    model: str = "deepseek-chat",
) -> MetricResult:
    """评估回答正确性（Answer Correctness）。

    检查回答与标准答案的一致程度。
    需要 ground_truth 才能计算。

    Args:
        question: 用户问题
        answer: LLM 生成的回答
        ground_truth: 标准答案
        model: 使用的 LLM 模型

    Returns:
        MetricResult 包含分数和详情
    """
    prompt = ANSWER_CORRECTNESS_PROMPT.format(
        question=question,
        answer=answer,
        ground_truth=ground_truth,
    )
    result = await evaluate_with_llm(prompt, model=model)
    score = _parse_score(result)

    return MetricResult(
        name="answer_correctness",
        score=score,
        details=result[:200] if result else "评估失败",
    )


async def evaluate_sample(
    query: str,
    contexts: list[str],
    answer: str,
    ground_truth: str = "",
    include_ground_truth: bool = False,
    model: str = "deepseek-chat",
) -> SampleEvaluation:
    """评估单条样本的所有指标。

    Args:
        query: 用户问题
        contexts: 检索到的文档片段列表
        answer: LLM 生成的回答
        ground_truth: 标准答案（可选）
        include_ground_truth: 是否计算需要 ground_truth 的指标
        model: 使用的 LLM 模型

    Returns:
        SampleEvaluation 包含所有指标的评估结果
    """
    # 并发执行不需要 ground_truth 的指标
    tasks = [
        evaluate_faithfulness(query, answer, contexts, model),
        evaluate_answer_relevancy(query, answer, model),
        evaluate_context_precision(query, contexts, model),
    ]

    # 如果有 ground_truth，添加需要它的指标
    if include_ground_truth and ground_truth:
        tasks.extend([
            evaluate_context_recall(query, ground_truth, contexts, model),
            evaluate_answer_correctness(query, answer, ground_truth, model),
        ])

    results = await asyncio.gather(*tasks, return_exceptions=True)

    metrics = []
    for r in results:
        if isinstance(r, MetricResult):
            metrics.append(r)
        elif isinstance(r, Exception):
            logger.error(f"指标评估失败: {r}")

    return SampleEvaluation(
        query=query,
        answer=answer,
        metrics=metrics,
    )


async def evaluate_batch(
    samples: list[dict],
    include_ground_truth: bool = False,
    model: str = "deepseek-chat",
    max_concurrency: int = 3,
) -> EvaluationResult:
    """批量评估多个样本。

    Args:
        samples: 样本列表，每个元素为 dict:
            - query: 用户问题
            - contexts: 检索到的文档片段列表
            - answer: LLM 生成的回答
            - ground_truth: 标准答案（可选）
        include_ground_truth: 是否计算需要 ground_truth 的指标
        model: 使用的 LLM 模型
        max_concurrency: 最大并发数

    Returns:
        EvaluationResult 包含所有样本的评估结果
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _eval_with_semaphore(sample):
        async with semaphore:
            return await evaluate_sample(
                query=sample.get("query", ""),
                contexts=sample.get("contexts", []),
                answer=sample.get("answer", ""),
                ground_truth=sample.get("ground_truth", ""),
                include_ground_truth=include_ground_truth,
                model=model,
            )

    tasks = [_eval_with_semaphore(s) for s in samples]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    eval_samples = []
    for r in results:
        if isinstance(r, SampleEvaluation):
            eval_samples.append(r)
        elif isinstance(r, Exception):
            logger.error(f"样本评估失败: {r}")

    return EvaluationResult(samples=eval_samples)
