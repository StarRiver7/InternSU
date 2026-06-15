"""RAG 评估执行器 — 编排完整的 Ragas 风格评估流程。

该模块是评估的核心入口，负责:
1. 接收评估数据集
2. 调用自定义指标进行评分
3. 汇总并输出结果

支持两种运行模式:
1. 离线评估: 从预构建的数据集文件加载数据
2. 在线评估: 直接从 RAG 管道运行结果评估

使用方式:
    # 方式 1: 离线评估
    evaluator = RAGEvaluator()
    report = await evaluator.evaluate_from_file("eval_data.jsonl")

    # 方式 2: 从管道结果评估
    evaluator = RAGEvaluator()
    report = await evaluator.evaluate_from_results(pipeline_results)

    # 方式 3: 自定义评估
    evaluator = RAGEvaluator()
    report = await evaluator.evaluate_single(query="...", contexts=[...], answer="...")
"""

import asyncio
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from app.evaluation.dataset_builder import DatasetBuilder, EvalSample, save_evaluation_dataset
from app.evaluation.metrics import (
    evaluate_batch,
    evaluate_sample,
    EvaluationResult,
    SampleEvaluation,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EvalReport:
    """评估报告数据结构。"""

    scores: dict[str, float] = field(default_factory=dict)
    sample_scores: list[dict] = field(default_factory=list)
    summary: str = ""
    elapsed_seconds: float = 0.0
    metric_names: list[str] = field(default_factory=list)
    sample_count: int = 0

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "scores": self.scores,
            "sample_scores": self.sample_scores,
            "summary": self.summary,
            "elapsed_seconds": self.elapsed_seconds,
            "metric_names": self.metric_names,
            "sample_count": self.sample_count,
        }


class RAGEvaluator:
    """InternSU RAG 评估执行器。

    使用示例:
        evaluator = RAGEvaluator()

        # 基础评估（无 ground_truth）
        report = await evaluator.evaluate_from_file("eval_data.jsonl")
        print(report.summary)

        # 完整评估（有 ground_truth）
        evaluator = RAGEvaluator(include_ground_truth=True)
        report = await evaluator.evaluate_from_file("eval_data_with_gt.jsonl")
    """

    def __init__(
        self,
        include_ground_truth: bool = False,
        model: str = "deepseek-chat",
        max_concurrency: int = 3,
    ):
        """初始化评估执行器。

        Args:
            include_ground_truth: 是否包含需要 ground_truth 的指标
            model: 使用的 LLM 模型
            max_concurrency: 最大并发评估数
        """
        self._include_ground_truth = include_ground_truth
        self._model = model
        self._max_concurrency = max_concurrency

    async def evaluate(
        self,
        samples: list[EvalSample],
    ) -> EvalReport:
        """执行评估。

        Args:
            samples: 评估样本列表

        Returns:
            EvalReport 评估报告
        """
        if not samples:
            raise ValueError("评估样本列表为空")

        logger.info(
            f"开始评估: {len(samples)} 条样本, "
            f"include_ground_truth={self._include_ground_truth}"
        )

        start = time.time()

        # 转换为评估格式
        eval_data = [
            {
                "query": s.query,
                "contexts": s.contexts,
                "answer": s.answer,
                "ground_truth": s.ground_truth,
            }
            for s in samples
        ]

        # 执行评估
        result = await evaluate_batch(
            samples=eval_data,
            include_ground_truth=self._include_ground_truth,
            model=self._model,
            max_concurrency=self._max_concurrency,
        )

        elapsed = time.time() - start

        # 生成报告
        report = self._generate_report(result, elapsed)
        logger.info(f"评估完成: {elapsed:.1f}s, 综合分: {report.overall_average:.4f}")
        return report

    async def evaluate_from_file(
        self,
        file_path: str,
        format: str = "jsonl",
    ) -> EvalReport:
        """从文件加载数据并执行评估。

        Args:
            file_path: 数据文件路径（jsonl 或 csv）
            format: 文件格式

        Returns:
            EvalReport 评估报告
        """
        builder = DatasetBuilder()

        if format == "jsonl":
            builder.build_from_jsonl(file_path)
        elif format == "csv":
            builder.build_from_csv(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {format}")

        samples = builder.build()
        return await self.evaluate(samples)

    async def evaluate_from_results(self, results: list[dict]) -> EvalReport:
        """从 RAG 管道运行结果列表执行评估。

        Args:
            results: RAG 管道运行结果列表

        Returns:
            EvalReport 评估报告
        """
        builder = DatasetBuilder()
        builder.build_from_pipeline_results(results)
        samples = builder.build()
        return await self.evaluate(samples)

    async def evaluate_single(
        self,
        query: str,
        contexts: list[str],
        answer: str,
        ground_truth: str = "",
    ) -> EvalReport:
        """评估单条查询。

        Args:
            query: 用户查询
            contexts: 检索到的上下文列表
            answer: LLM 生成的回答
            ground_truth: 标准答案（可选）

        Returns:
            EvalReport 评估报告
        """
        builder = DatasetBuilder()
        builder.add_sample(
            query=query,
            contexts=contexts,
            answer=answer,
            ground_truth=ground_truth,
        )
        samples = builder.build()
        return await self.evaluate(samples)

    def _generate_report(
        self,
        result: EvaluationResult,
        elapsed: float,
    ) -> EvalReport:
        """生成评估报告。"""
        report = EvalReport()
        report.elapsed_seconds = elapsed
        report.sample_count = len(result.samples)

        # 计算平均分
        avgs = result.average_scores
        report.scores = avgs
        report.metric_names = list(avgs.keys())

        # 每条样本的分数
        report.sample_scores = [
            {
                "query": s.query,
                **s.scores,
            }
            for s in result.samples
        ]

        # 生成摘要
        report.summary = self._generate_summary(report)
        return report

    def _generate_summary(self, report: EvalReport) -> str:
        """生成人类可读的评估摘要。"""
        lines = [
            "=" * 60,
            "RAG 评估报告 (Ragas 指标体系)",
            "=" * 60,
            f"样本数量: {report.sample_count}",
            f"评估耗时: {report.elapsed_seconds:.1f}s",
            f"评估指标: {', '.join(report.metric_names)}",
            "-" * 60,
        ]

        for metric, score in report.scores.items():
            # 评级
            if score >= 0.8:
                grade = "★★★ 优秀"
            elif score >= 0.6:
                grade = "★★☆ 良好"
            elif score >= 0.4:
                grade = "★☆☆ 一般"
            else:
                grade = "☆☆☆ 较差"

            lines.append(f"  {metric:<25s} {score:.4f}  {grade}")

        # 综合评分
        if report.scores:
            avg = sum(report.scores.values()) / len(report.scores)
            lines.append("-" * 60)
            lines.append(f"  {'综合评分':<25s} {avg:.4f}")

            if avg >= 0.8:
                lines.append("  结论: RAG 系统表现优秀，检索和生成质量均达到高水平")
            elif avg >= 0.6:
                lines.append("  结论: RAG 系统表现良好，有小幅优化空间")
            elif avg >= 0.4:
                lines.append("  结论: RAG 系统表现一般，建议重点优化薄弱环节")
            else:
                lines.append("  结论: RAG 系统需要较大改进，建议全面排查检索和生成环节")

        # 每条样本的详细分数
        lines.append("=" * 60)
        lines.append("每条样本详细分数:")
        lines.append("-" * 60)
        for i, s in enumerate(report.sample_scores, 1):
            query = s.get("query", "")[:40]
            scores_str = ", ".join(
                f"{k}={v:.2f}" for k, v in s.items() if k != "query"
            )
            lines.append(f"  [{i}] {query}...")
            lines.append(f"      {scores_str}")

        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def save_report(report: EvalReport, output_path: str) -> None:
        """将评估报告保存为 JSON 文件。

        Args:
            report: 评估报告
            output_path: 输出文件路径
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"评估报告已保存到 {path}")

    @staticmethod
    def print_report(report: EvalReport) -> None:
        """打印评估报告到控制台。"""
        print(report.summary)
