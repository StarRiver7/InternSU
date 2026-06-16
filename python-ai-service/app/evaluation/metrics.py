"""Ragas 核心指标自定义实现 —— 基于 LLM Judge 的 RAG 评估指标体系。

【架构定位】
该模块是 Ragas 评估框架的核心指标层，自定义实现了 5 个 Ragas 标准指标，
通过 InternSU LLM Gateway 调用 DeepSeek V3 作为 LLM-as-Judge 进行评分。

【指标体系】

  1. Faithfulness (忠实度):
     回答是否基于检索到的上下文，有无幻觉（编造内容）
     评估逻辑：将回答中的每个声明与上下文逐一比对

  2. Answer Relevancy (回答相关性):
     回答是否真正回答了用户的问题
     评估逻辑：检查回答与问题的语义匹配度

  3. Context Precision (上下文精确率):
     检索到的上下文中，有多少是与问题相关的
     评估逻辑：检查每个检索片段与问题的相关性

  4. Context Recall (上下文召回率):
     检索是否覆盖了回答问题所需的所有信息（需 ground_truth）
     评估逻辑：将 ground_truth 中的信息点与上下文逐一比对

  5. Answer Correctness (回答正确性):
     回答与标准答案的一致程度（需 ground_truth）
     评估逻辑：将回答与 ground_truth 进行语义和事实比对

【评分机制】
每个指标通过精心设计的 Prompt 要求 LLM 返回 0-1 的数字分数，
评分标准分为 6 个等级（0.0/0.2/0.4/0.6/0.8/1.0），
低温度参数（temperature=0.1）保证评分的稳定性和可重复性。

【使用方式】
    from app.evaluation.metrics import evaluate_sample
    result = await evaluate_sample(
        query="校训是什么",
        contexts=["校训: 博学笃行厚德创新"],
        answer="校训是博学笃行厚德创新",
    )
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from app.evaluation.ragas_config import evaluate_with_llm, evaluate_with_llm_json
from app.core.logger import get_logger

logger = get_logger(__name__)


# ── 指标评分 Prompt 模板 ─────────────────────────────────────────────
# 每个 Prompt 定义了 6 级评分标准，要求 LLM 仅返回数字分数

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


# ── 数据结构定义 ────────────────────────────────────────────────────

@dataclass
class MetricResult:
    """单个指标的评估结果。

    Attributes:
        name: 指标名称（如 faithfulness, answer_relevancy）
        score: 评估分数 [0, 1]
        details: LLM 返回的原始评估文本（用于调试）
    """
    name: str
    score: float
    details: str = ""


@dataclass
class SampleEvaluation:
    """单条样本的完整评估结果。

    包含所有指标的评分，支持按指标名查询分数和计算平均分。

    Attributes:
        query: 用户原始问题
        answer: LLM 生成的回答
        metrics: 各指标的评估结果列表
    """
    query: str
    answer: str
    metrics: list[MetricResult] = field(default_factory=list)

    @property
    def scores(self) -> dict[str, float]:
        """返回 {指标名: 分数} 的字典。"""
        return {m.name: m.score for m in self.metrics}

    @property
    def average_score(self) -> float:
        """计算所有指标的平均分。"""
        if not self.metrics:
            return 0.0
        return sum(m.score for m in self.metrics) / len(self.metrics)


@dataclass
class EvaluationResult:
    """批量评估的完整结果。

    支持按指标名计算各指标的平均分和总平均分。

    Attributes:
        samples: 所有样本的评估结果列表
    """
    samples: list[SampleEvaluation] = field(default_factory=list)

    @property
    def metric_names(self) -> list[str]:
        """返回所有指标名称列表。"""
        if not self.samples:
            return []
        return list(self.samples[0].scores.keys())

    @property
    def average_scores(self) -> dict[str, float]:
        """计算各指标在所有样本上的平均分。"""
        if not self.samples:
            return {}
        names = self.metric_names
        return {
            name: sum(s.scores.get(name, 0) for s in self.samples) / len(self.samples)
            for name in names
        }

    @property
    def overall_average(self) -> float:
        """计算所有指标、所有样本的总平均分。"""
        avgs = self.average_scores
        if not avgs:
            return 0.0
        return sum(avgs.values()) / len(avgs)


# ── 分数解析工具 ────────────────────────────────────────────────────

def _parse_score(text: str) -> float:
    """从 LLM 返回的文本中解析 0-1 的数字分数。

    支持三种格式：
    1. 纯数字（如 "0.85"）
    2. 嵌入文本的数字（如 "分数是 0.75 分"）
    3. 无法解析时返回 0.0

    Args:
        text: LLM 返回的评估文本

    Returns:
        解析后的分数 [0, 1]
    """
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


# ── 指标评估函数 ────────────────────────────────────────────────────

async def evaluate_faithfulness(
    question: str,
    answer: str,
    contexts: list[str],
    model: str = "deepseek-chat",
) -> MetricResult:
    """评估回答忠实度（Faithfulness）。

    检查回答中的每个声明是否在检索上下文中有依据，
    用于检测 LLM 幻觉（编造内容）。

    Args:
        question: 用户原始问题
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

    检查回答是否真正回答了用户的问题，而非答非所问。

    Args:
        question: 用户原始问题
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

    检查检索到的上下文中，有多少是与问题相关的，
    用于评估检索系统的精确率。

    Args:
        question: 用户原始问题
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
    需要 ground_truth（标准答案）才能计算。

    Args:
        question: 用户原始问题
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
        question: 用户原始问题
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


# ── 样本级评估编排 ──────────────────────────────────────────────────

async def evaluate_sample(
    query: str,
    contexts: list[str],
    answer: str,
    ground_truth: str = "",
    include_ground_truth: bool = False,
    model: str = "deepseek-chat",
) -> SampleEvaluation:
    """评估单条样本的所有指标。

    并发执行不需要 ground_truth 的 3 个指标，
    如果有 ground_truth 则额外执行 2 个指标。

    Args:
        query: 用户原始问题
        contexts: 检索到的文档片段列表
        answer: LLM 生成的回答
        ground_truth: 标准答案（可选）
        include_ground_truth: 是否计算需要 ground_truth 的指标
        model: 使用的 LLM 模型

    Returns:
        SampleEvaluation 包含所有指标的评估结果
    """
    # 并发执行不需要 ground_truth 的核心指标
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


# ── 批量评估编排 ────────────────────────────────────────────────────

async def evaluate_batch(
    samples: list[dict],
    include_ground_truth: bool = False,
    model: str = "deepseek-chat",
    max_concurrency: int = 3,
) -> EvaluationResult:
    """批量评估多个样本，支持并发控制。

    使用 asyncio.Semaphore 控制并发数，避免 LLM API 过载。
    每个样本独立评估，失败的样本不会影响其他样本。

    Args:
        samples: 样本列表，每个元素为 dict:
            - query: 用户问题
            - contexts: 检索到的文档片段列表
            - answer: LLM 生成的回答
            - ground_truth: 标准答案（可选）
        include_ground_truth: 是否计算需要 ground_truth 的指标
        model: 使用的 LLM 模型
        max_concurrency: 最大并发评估数

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
