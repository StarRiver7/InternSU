"""RAG 评估框架单元测试。

验证:
  1. DatasetBuilder 能正确构建评估样本
  2. 从 JSONL/CSV 文件加载数据
  3. 从 RAG 管道结果构建数据
  4. 从 LangGraph 状态构建数据
  5. 评估报告生成和序列化
  6. 指标评分函数正常工作
"""

import json
import tempfile
import os
import pytest
from pathlib import Path
from pytest import approx

from app.evaluation.dataset_builder import DatasetBuilder, save_evaluation_dataset, EvalSample
from app.evaluation.evaluator import RAGEvaluator, EvalReport
from app.evaluation.metrics import (
    _parse_score,
    MetricResult,
    SampleEvaluation,
    EvaluationResult,
)


class TestDatasetBuilder:
    """测试 DatasetBuilder 数据集构建功能。"""

    def test_add_sample(self):
        """测试添加单条样本。"""
        builder = DatasetBuilder()
        builder.add_sample(
            query="公司报销流程",
            contexts=["报销需提前申请"],
            answer="收到老师～报销需提前申请",
            ground_truth="报销需提前申请",
        )
        samples = builder.build()
        assert len(samples) == 1
        assert samples[0].query == "公司报销流程"
        assert len(samples[0].contexts) == 1
        assert samples[0].contexts[0] == "报销需提前申请"
        assert samples[0].answer == "收到老师～报销需提前申请"
        assert samples[0].ground_truth == "报销需提前申请"

    def test_add_sample_chaining(self):
        """测试链式调用添加多条样本。"""
        builder = DatasetBuilder()
        builder.add_sample(
            query="问题1",
            contexts=["上下文1"],
            answer="回答1",
        ).add_sample(
            query="问题2",
            contexts=["上下文2"],
            answer="回答2",
        )
        samples = builder.build()
        assert len(samples) == 2
        assert samples[0].query == "问题1"
        assert samples[1].query == "问题2"

    def test_build_samples(self):
        """测试构建样本列表。"""
        builder = DatasetBuilder()
        builder.add_sample(
            query="测试问题",
            contexts=["测试上下文"],
            answer="测试回答",
        )
        samples = builder.build()
        assert len(samples) == 1
        assert samples[0].query == "测试问题"
        assert samples[0].contexts == ["测试上下文"]
        assert samples[0].answer == "测试回答"

    def test_build_empty_raises(self):
        """测试空数据集构建抛出异常。"""
        builder = DatasetBuilder()
        with pytest.raises(ValueError, match="没有评估样本"):
            builder.build()

    def test_build_from_pipeline_result(self):
        """测试从 RAG 管道结果构建数据。"""
        result = {
            "query": "报销流程",
            "merged_chunks": [
                {"content": "报销需提前申请"},
                {"content": "报销金额上限5000元"},
            ],
            "answer": "收到老师～报销需提前申请",
            "trust_level": "high",
            "retrieval_count": 2,
        }
        builder = DatasetBuilder()
        builder.build_from_pipeline_result(result)
        samples = builder.build()
        assert len(samples) == 1
        assert samples[0].query == "报销流程"
        assert len(samples[0].contexts) == 2
        assert samples[0].metadata["trust_level"] == "high"

    def test_build_from_pipeline_result_with_context_text(self):
        """测试从管道结果的 context_text 解析 contexts。"""
        result = {
            "query": "年假",
            "context_text": (
                "[Source 1] (relevance: 0.92) from 员工手册.pdf\n"
                "员工每年享有10天带薪年假\n"
                "---\n"
                "[Source 2] (relevance: 0.87) from HR政策.pdf\n"
                "年假需提前3天申请"
            ),
            "answer": "年假有10天",
        }
        builder = DatasetBuilder()
        builder.build_from_pipeline_result(result)
        samples = builder.build()
        assert len(samples[0].contexts) == 2

    def test_build_from_langgraph_state(self):
        """测试从 LangGraph 状态构建数据。"""
        state = {
            "user_message": "报销流程",
            "retrieval_results": [
                {"content": "报销需提前申请"},
                {"content": "报销金额上限5000元"},
            ],
            "rag_answer": "收到老师～报销需提前申请",
            "trust_level": "medium",
            "retrieval_count": 2,
            "intent": "rag",
            "selected_tool": "rag",
        }
        builder = DatasetBuilder()
        builder.build_from_langgraph_state(state)
        samples = builder.build()
        assert len(samples) == 1
        assert samples[0].query == "报销流程"
        assert len(samples[0].contexts) == 2
        assert samples[0].metadata["intent"] == "rag"

    def test_build_from_jsonl(self):
        """测试从 JSONL 文件加载数据。"""
        data = [
            {"query": "问题1", "contexts": ["上下文1"], "answer": "回答1", "ground_truth": "标准1"},
            {"query": "问题2", "contexts": ["上下文2", "上下文3"], "answer": "回答2", "ground_truth": "标准2"},
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            tmp_path = f.name

        try:
            builder = DatasetBuilder()
            builder.build_from_jsonl(tmp_path)
            samples = builder.build()
            assert len(samples) == 2
            assert samples[0].query == "问题1"
            assert len(samples[1].contexts) == 2
        finally:
            os.unlink(tmp_path)

    def test_build_from_csv(self):
        """测试从 CSV 文件加载数据。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as f:
            f.write("query,contexts,answer,ground_truth\n")
            f.write('"问题1","[\"上下文1\"]","回答1","标准1"\n')
            f.write('"问题2","[\"上下文2\"]","回答2","标准2"\n')
            tmp_path = f.name

        try:
            builder = DatasetBuilder()
            builder.build_from_csv(tmp_path)
            samples = builder.build()
            assert len(samples) == 2
            assert samples[0].query == "问题1"
        finally:
            os.unlink(tmp_path)

    def test_save_and_load_jsonl(self):
        """测试保存和加载 JSONL 数据集。"""
        builder = DatasetBuilder()
        builder.add_sample(
            query="测试问题",
            contexts=["测试上下文"],
            answer="测试回答",
            ground_truth="标准答案",
        )
        samples = builder.build()

        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", delete=False
        ) as f:
            tmp_path = f.name

        try:
            save_evaluation_dataset(samples, tmp_path, format="jsonl")

            # 验证文件内容
            with open(tmp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 1
            row = json.loads(lines[0])
            assert row["query"] == "测试问题"
            assert row["contexts"] == ["测试上下文"]
            assert row["answer"] == "测试回答"
            assert row["ground_truth"] == "标准答案"
        finally:
            os.unlink(tmp_path)

    def test_metadata_preserved(self):
        """测试元数据在构建过程中被保留。"""
        builder = DatasetBuilder()
        builder.add_sample(
            query="问题",
            contexts=["上下文"],
            answer="回答",
            metadata={"trust_level": "high", "elapsed_ms": 150},
        )
        samples = builder.build()
        assert samples[0].metadata["trust_level"] == "high"
        assert samples[0].metadata["elapsed_ms"] == 150


class TestEvalReport:
    """测试评估报告数据结构。"""

    def test_report_serialization(self):
        """测试报告序列化为字典。"""
        report = EvalReport(
            scores={"faithfulness": 0.85, "answer_relevancy": 0.92},
            sample_scores=[{"query": "test", "faithfulness": 0.85}],
            summary="测试摘要",
            elapsed_seconds=1.5,
            metric_names=["faithfulness", "answer_relevancy"],
            sample_count=1,
        )
        d = report.to_dict()
        assert d["scores"]["faithfulness"] == 0.85
        assert d["sample_count"] == 1
        assert d["elapsed_seconds"] == 1.5

    def test_report_save_and_load(self):
        """测试报告保存和加载。"""
        report = EvalReport(
            scores={"faithfulness": 0.85},
            summary="测试摘要",
            elapsed_seconds=1.0,
            sample_count=1,
        )

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            tmp_path = f.name

        try:
            RAGEvaluator.save_report(report, tmp_path)

            with open(tmp_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["scores"]["faithfulness"] == 0.85
            assert loaded["summary"] == "测试摘要"
        finally:
            os.unlink(tmp_path)


class TestParseScore:
    """测试分数解析函数。"""

    def test_parse_float(self):
        """测试解析浮点数。"""
        assert _parse_score("0.85") == 0.85
        assert _parse_score("1.0") == 1.0
        assert _parse_score("0.0") == 0.0

    def test_parse_in_text(self):
        """测试从文本中提取数字。"""
        assert _parse_score("分数是 0.75 分") == 0.75
        assert _parse_score("0.85 是一个好分数") == 0.85

    def test_parse_clamp(self):
        """测试分数范围限制。"""
        assert _parse_score("1.5") == 1.0
        assert _parse_score("-0.5") == 0.0

    def test_parse_invalid(self):
        """测试无效输入。"""
        assert _parse_score("无法解析") == 0.0
        assert _parse_score("") == 0.0


class TestMetricResult:
    """测试指标结果数据结构。"""

    def test_metric_result(self):
        """测试 MetricResult 创建。"""
        result = MetricResult(name="faithfulness", score=0.85, details="测试详情")
        assert result.name == "faithfulness"
        assert result.score == 0.85
        assert result.details == "测试详情"


class TestSampleEvaluation:
    """测试样本评估结果。"""

    def test_scores_property(self):
        """测试 scores 属性。"""
        eval_result = SampleEvaluation(
            query="测试",
            answer="回答",
            metrics=[
                MetricResult(name="faithfulness", score=0.85),
                MetricResult(name="answer_relevancy", score=0.92),
            ],
        )
        assert eval_result.scores == {"faithfulness": 0.85, "answer_relevancy": 0.92}

    def test_average_score(self):
        """测试 average_score 属性。"""
        eval_result = SampleEvaluation(
            query="测试",
            answer="回答",
            metrics=[
                MetricResult(name="faithfulness", score=0.80),
                MetricResult(name="answer_relevancy", score=0.90),
            ],
        )
        assert eval_result.average_score == approx(0.85, abs=1e-10)

    def test_average_score_empty(self):
        """测试空指标的平均分。"""
        eval_result = SampleEvaluation(
            query="测试",
            answer="回答",
            metrics=[],
        )
        assert eval_result.average_score == 0.0


class TestEvaluationResult:
    """测试批量评估结果。"""

    def test_average_scores(self):
        """测试各指标平均分。"""
        result = EvaluationResult(
            samples=[
                SampleEvaluation(
                    query="q1", answer="a1",
                    metrics=[
                        MetricResult(name="faithfulness", score=0.80),
                        MetricResult(name="answer_relevancy", score=0.90),
                    ],
                ),
                SampleEvaluation(
                    query="q2", answer="a2",
                    metrics=[
                        MetricResult(name="faithfulness", score=0.60),
                        MetricResult(name="answer_relevancy", score=0.80),
                    ],
                ),
            ]
        )
        avgs = result.average_scores
        assert avgs["faithfulness"] == 0.70
        assert avgs["answer_relevancy"] == approx(0.85, abs=1e-10)

    def test_overall_average(self):
        """测试总平均分。"""
        result = EvaluationResult(
            samples=[
                SampleEvaluation(
                    query="q1", answer="a1",
                    metrics=[
                        MetricResult(name="faithfulness", score=0.80),
                        MetricResult(name="answer_relevancy", score=0.90),
                    ],
                ),
            ]
        )
        assert result.overall_average == approx(0.85, abs=1e-10)


class TestParseContextText:
    """测试上下文文本解析。"""

    def test_parse_standard_format(self):
        """测试解析标准格式上下文。"""
        text = (
            "[Source 1] (relevance: 0.92) from 员工手册.pdf\n"
            "员工每年享有10天带薪年假\n"
            "---\n"
            "[Source 2] (relevance: 0.87) from HR政策.pdf\n"
            "年假需提前3天申请"
        )
        contexts = DatasetBuilder._parse_context_text(text)
        assert len(contexts) == 2
        assert "员工每年享有10天带薪年假" in contexts[0]
        assert "年假需提前3天申请" in contexts[1]

    def test_parse_empty_text(self):
        """测试解析空文本。"""
        contexts = DatasetBuilder._parse_context_text("")
        assert contexts == []

    def test_parse_single_source(self):
        """测试解析单个 Source。"""
        text = "[Source 1] from 文档.pdf\n报销需提前申请"
        contexts = DatasetBuilder._parse_context_text(text)
        assert len(contexts) == 1
        assert "报销需提前申请" in contexts[0]


class TestRAGEvaluator:
    """测试评估执行器初始化。"""

    def test_evaluator_init(self):
        """测试评估器初始化。"""
        evaluator = RAGEvaluator()
        assert evaluator._include_ground_truth is False
        assert evaluator._model == "deepseek-chat"
        assert evaluator._max_concurrency == 3

    def test_evaluator_with_ground_truth(self):
        """测试带 ground_truth 的评估器初始化。"""
        evaluator = RAGEvaluator(include_ground_truth=True)
        assert evaluator._include_ground_truth is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
