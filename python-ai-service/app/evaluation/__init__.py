"""RAG 评估模块 — 基于 Ragas 指标体系的自定义实现。

该模块为 InternSU RAG 管道提供自动化评估能力，
采用 Ragas 核心指标体系（Faithfulness, Answer Relevance, Context Precision 等），
通过项目的 LLM Gateway 直接调用 LLM 进行评分，避免外部依赖冲突。

核心指标:
- Faithfulness: 回答是否基于检索上下文（防幻觉）
- Answer Relevance: 回答是否真正回答了用户的问题
- Context Precision: 检索结果中相关文档的比例
- Context Recall: 检索是否覆盖了所有必要信息（需 ground_truth）
- Answer Correctness: 与标准答案的一致程度（需 ground_truth）
"""
