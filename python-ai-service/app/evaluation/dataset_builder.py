"""数据集构建器 — 将 InternSU RAG 管道数据转换为评估数据集。

评估需要以下字段:
- query: 用户原始问题
- contexts: 检索到的文档片段列表
- answer: LLM 生成的回答
- ground_truth: (可选) 标准答案

本模块负责从以下数据源组装上述字段:
1. 直接采集: 通过 RAG 管道运行后采集 query/contexts/answer
2. 标注文件: 从 JSONL/CSV 格式的标注文件加载 ground_truth
3. 批量构建: 从多个评估样本构建数据集

使用方式:
    # 方式 1: 从管道运行结果构建
    builder = DatasetBuilder()
    samples = builder.build_from_pipeline_results(results)

    # 方式 2: 从标注文件构建
    samples = builder.build_from_file("eval_data.jsonl")
"""

import json
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EvalSample:
    """单条评估样本。"""

    query: str
    contexts: list[str]
    answer: str
    ground_truth: str = ""
    metadata: dict = field(default_factory=dict)


class DatasetBuilder:
    """将 InternSU RAG 管道数据转换为评估样本列表。

    支持三种数据来源:
    1. 管道直接运行结果 (build_from_pipeline_result)
    2. JSONL 标注文件 (build_from_jsonl)
    3. 手动构建 (add_sample + build)

    使用示例:
        builder = DatasetBuilder()

        # 添加样本
        builder.add_sample(
            query="公司报销流程是什么",
            contexts=["报销需提前申请...", "报销金额上限为..."],
            answer="收到老师～公司报销流程为...",
            ground_truth="员工需填写报销单，经部门经理审批后提交财务部...",
        )

        # 构建样本列表
        samples = builder.build()
    """

    def __init__(self):
        self._samples: list[EvalSample] = []

    def add_sample(
        self,
        query: str,
        contexts: list[str],
        answer: str,
        ground_truth: str = "",
        metadata: Optional[dict] = None,
    ) -> "DatasetBuilder":
        """添加单条评估样本。

        Args:
            query: 用户原始问题
            contexts: 检索到的文档片段列表（每个元素为一段文本）
            answer: LLM 生成的回答
            ground_truth: 标准答案（可选，用于 Answer Correctness 评估）
            metadata: 额外元数据（如 trust_level, retrieval_count 等）

        Returns:
            self (支持链式调用)
        """
        self._samples.append(EvalSample(
            query=query,
            contexts=contexts,
            answer=answer,
            ground_truth=ground_truth,
            metadata=metadata or {},
        ))
        return self

    def build_from_pipeline_result(self, result: dict) -> "DatasetBuilder":
        """从单条 RAG 管道运行结果构建评估样本。

        适配 RetrievalPipeline.retrieve() 返回的 RetrievalResult 结构。

        Args:
            result: RAG 管道运行结果字典，包含:
                - query: 用户查询
                - chunks/merged_chunks: 检索到的文档片段
                - context_text: 格式化的上下文
                - answer/rag_answer: LLM 生成的回答
                - ground_truth: 标准答案（可选）
        """
        query = result.get("query", "")
        answer = result.get("answer") or result.get("rag_answer", "")

        # 从 chunks 提取 contexts
        chunks = result.get("merged_chunks") or result.get("chunks", [])
        contexts = []
        for chunk in chunks:
            content = chunk.get("content", "")
            if content:
                contexts.append(content)

        # 如果没有 chunks 但有 context_text，从格式化文本中提取
        if not contexts and result.get("context_text"):
            contexts = self._parse_context_text(result["context_text"])

        ground_truth = result.get("ground_truth", "")

        return self.add_sample(
            query=query,
            contexts=contexts,
            answer=answer,
            ground_truth=ground_truth,
            metadata={
                "trust_level": result.get("trust_level", "medium"),
                "retrieval_count": result.get("retrieval_count", 0),
                "elapsed_ms": result.get("elapsed_ms", 0),
            },
        )

    def build_from_pipeline_results(self, results: list[dict]) -> "DatasetBuilder":
        """批量从管道运行结果构建评估样本。"""
        for r in results:
            self.build_from_pipeline_result(r)
        return self

    def build_from_langgraph_state(self, state: dict) -> "DatasetBuilder":
        """从 LangGraph InternState 构建评估样本。

        适配 app.graph.state.InternState 的字段结构。

        Args:
            state: LangGraph 状态字典，包含:
                - user_message: 用户查询
                - retrieval_results: 检索结果列表
                - rag_context: 格式化后的 RAG 上下文
                - rag_answer/final_answer: LLM 生成的回答
                - ground_truth: 标准答案（可选）
        """
        query = state.get("user_message", "")
        answer = state.get("rag_answer") or state.get("final_answer", "")

        # 从 retrieval_results 提取 contexts
        retrieval_results = state.get("retrieval_results", [])
        contexts = [r.get("content", "") for r in retrieval_results if r.get("content")]

        # 如果没有直接的 chunks，从 rag_context 解析
        if not contexts and state.get("rag_context"):
            contexts = self._parse_context_text(state["rag_context"])

        ground_truth = state.get("ground_truth", "")

        return self.add_sample(
            query=query,
            contexts=contexts,
            answer=answer,
            ground_truth=ground_truth,
            metadata={
                "trust_level": state.get("trust_level", "medium"),
                "retrieval_count": state.get("retrieval_count", 0),
                "intent": state.get("intent", ""),
                "selected_tool": state.get("selected_tool", ""),
            },
        )

    def build_from_jsonl(self, file_path: str) -> "DatasetBuilder":
        """从 JSONL 标注文件加载评估样本。

        JSONL 文件每行一个 JSON 对象，格式:
        {
            "query": "公司报销流程是什么",
            "contexts": ["报销需提前申请...", "报销金额上限为..."],
            "answer": "收到老师～公司报销流程为...",
            "ground_truth": "员工需填写报销单..."
        }

        Args:
            file_path: JSONL 文件路径
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"评估数据文件不存在: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self.add_sample(
                        query=data.get("query", ""),
                        contexts=data.get("contexts", []),
                        answer=data.get("answer", ""),
                        ground_truth=data.get("ground_truth", ""),
                        metadata=data.get("metadata", {}),
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONL 第 {line_num} 行解析失败: {e}")

        logger.info(f"从 {file_path} 加载了 {len(self._samples)} 条评估样本")
        return self

    def build_from_csv(self, file_path: str) -> "DatasetBuilder":
        """从 CSV 文件加载评估样本。

        CSV 列: query, contexts (JSON array), answer, ground_truth (可选)

        Args:
            file_path: CSV 文件路径
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"评估数据文件不存在: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                contexts_raw = row.get("contexts", "[]")
                try:
                    contexts = json.loads(contexts_raw) if contexts_raw else []
                except json.JSONDecodeError:
                    contexts = [contexts_raw] if contexts_raw else []

                self.add_sample(
                    query=row.get("query", ""),
                    contexts=contexts,
                    answer=row.get("answer", ""),
                    ground_truth=row.get("ground_truth", ""),
                )

        logger.info(f"从 {file_path} 加载了 {len(self._samples)} 条评估样本")
        return self

    def build(self) -> list[EvalSample]:
        """构建评估样本列表。

        Returns:
            评估样本列表，可直接传入 evaluate_batch()
        """
        if not self._samples:
            raise ValueError("没有评估样本可构建数据集，请先添加样本")
        return list(self._samples)

    @staticmethod
    def _parse_context_text(context_text: str) -> list[str]:
        """从格式化的 RAG 上下文文本中解析出各个 Source 片段。

        上下文格式示例:
            [Source 1] (relevance: 0.92) from 员工手册.pdf page 5
            年假需提前3天向直属领导申请...
            ---
            [Source 2] (relevance: 0.87) from HR政策.pdf
            员工每年享有10天带薪年假...
        """
        if not context_text:
            return []

        # 按分隔符分割
        parts = context_text.split("---")
        contexts = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 移除 [Source N] 标题行
            lines = part.split("\n")
            content_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith("[Source"):
                    continue
                if line:
                    content_lines.append(line)
            if content_lines:
                contexts.append("\n".join(content_lines))

        return contexts


def save_evaluation_dataset(
    samples: list[EvalSample],
    output_path: str,
    format: str = "jsonl",
) -> None:
    """将评估数据集保存为文件。

    Args:
        samples: 评估样本列表
        output_path: 输出文件路径
        format: 输出格式 (jsonl/csv)
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if format == "jsonl":
        with open(path, "w", encoding="utf-8") as f:
            for sample in samples:
                row = {
                    "query": sample.query,
                    "contexts": sample.contexts,
                    "answer": sample.answer,
                    "ground_truth": sample.ground_truth,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    elif format == "csv":
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["query", "contexts", "answer", "ground_truth"])
            writer.writeheader()
            for sample in samples:
                writer.writerow({
                    "query": sample.query,
                    "contexts": json.dumps(sample.contexts, ensure_ascii=False),
                    "answer": sample.answer,
                    "ground_truth": sample.ground_truth,
                })
    else:
        raise ValueError(f"不支持的格式: {format}")

    logger.info(f"评估数据集已保存到 {path}")
