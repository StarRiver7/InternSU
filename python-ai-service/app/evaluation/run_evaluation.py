"""RAG 评估入口 — 命令行运行 Ragas 风格评估。

使用方式:
    # 从 JSONL 文件评估
    python -m app.evaluation.run_evaluation --file eval_data.jsonl

    # 从 CSV 文件评估
    python -m app.evaluation.run_evaluation --file eval_data.csv --format csv

    # 包含 ground_truth 指标
    python -m app.evaluation.run_evaluation --file eval_data.jsonl --with-gt

    # 输出报告到文件
    python -m app.evaluation.run_evaluation --file eval_data.jsonl --output report.json

    # 运行示例评估（使用内置测试数据）
    python -m app.evaluation.run_evaluation --demo
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.evaluation.evaluator import RAGEvaluator
from app.evaluation.dataset_builder import DatasetBuilder, save_evaluation_dataset, EvalSample
from app.core.logger import get_logger

logger = get_logger(__name__)


def _create_demo_samples() -> list[EvalSample]:
    """创建示例评估样本（用于快速验证评估流程）。"""
    builder = DatasetBuilder()

    builder.add_sample(
        query="公司报销流程是什么",
        contexts=[
            "员工报销需提前填写《费用报销申请单》，经部门经理审批后提交财务部。"
            "报销金额超过5000元需总经理审批。报销单需附发票原件。",
            "差旅费报销标准：高铁二等座、飞机经济舱。住宿标准：一线城市500元/天，"
            "二线城市350元/天。餐费补贴：100元/天。",
        ],
        answer="收到老师～公司报销流程如下：\n"
               "1. 填写《费用报销申请单》\n"
               "2. 经部门经理审批\n"
               "3. 提交财务部 [来源1]\n"
               "4. 超过5000元需总经理审批 [来源1]\n"
               "差旅费标准：高铁二等座、经济舱，住宿一线500元/天、二线350元/天 [来源2]",
        ground_truth="员工需填写报销申请单，经部门经理审批后提交财务部。"
                     "超过5000元需总经理审批。差旅费标准包括交通、住宿和餐费补贴。",
    )

    builder.add_sample(
        query="年假有多少天",
        contexts=[
            "员工入职满一年后享有5天带薪年假，满十年后享有10天带薪年假。"
            "年假需提前3天向直属领导申请。",
            "年假可跨年度使用，但需在次年3月31日前使用完毕。"
            "未使用的年假不折算工资。",
        ],
        answer="收到老师～根据公司规定：\n"
               "入职满1年：5天带薪年假 [来源1]\n"
               "入职满10年：10天带薪年假 [来源1]\n"
               "需提前3天向直属领导申请 [来源1]\n"
               "年假可跨年度使用，但需在次年3月31日前用完 [来源2]",
        ground_truth="入职满一年5天年假，满十年10天年假。需提前3天申请。"
                     "可跨年度使用但需在次年3月31日前用完。",
    )

    builder.add_sample(
        query="迟到怎么处罚",
        contexts=[
            "迟到30分钟以内每次扣款50元，迟到30分钟至1小时扣款100元。"
            "每月累计迟到3次以上扣发当月全勤奖。",
            "特殊情况（如交通管制、恶劣天气）经部门负责人确认可免于处罚。"
            "因公外出需提前报备。",
        ],
        answer="收到老师～迟到处罚规定如下：\n"
               "30分钟以内：扣款50元 [来源1]\n"
               "30分钟至1小时：扣款100元 [来源1]\n"
               "每月累计3次以上：扣发全勤奖 [来源1]\n"
               "特殊情况（交通管制、恶劣天气）经确认可免罚 [来源2]",
        ground_truth="30分钟以内扣50元，30分钟至1小时扣100元。"
                     "每月累计3次以上扣全勤奖。特殊情况可免罚。",
    )

    return builder.build()


async def main():
    parser = argparse.ArgumentParser(
        description="InternSU RAG 评估工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从文件评估
  python -m app.evaluation.run_evaluation --file eval_data.jsonl

  # 运行 Demo 评估
  python -m app.evaluation.run_evaluation --demo

  # 包含 ground_truth 指标
  python -m app.evaluation.run_evaluation --file data.jsonl --with-gt
        """,
    )

    parser.add_argument(
        "--file", "-f",
        help="评估数据文件路径 (jsonl 或 csv)",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "csv"],
        default="jsonl",
        help="数据文件格式 (默认: jsonl)",
    )
    parser.add_argument(
        "--output", "-o",
        help="评估报告输出路径 (JSON 格式)",
    )
    parser.add_argument(
        "--with-gt",
        action="store_true",
        help="包含需要 ground_truth 的指标 (Context Recall, Answer Correctness)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用内置示例数据运行评估",
    )
    parser.add_argument(
        "--save-dataset",
        help="将评估数据集保存为文件",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=3,
        help="最大并发评估数 (默认: 3)",
    )
    parser.add_argument(
        "--model",
        default="deepseek-chat",
        help="使用的 LLM 模型 (默认: deepseek-chat)",
    )

    args = parser.parse_args()

    if not args.file and not args.demo:
        parser.print_help()
        print("\n错误: 请指定 --file 或 --demo")
        sys.exit(1)

    # 构建数据集
    if args.demo:
        logger.info("使用内置示例数据运行评估...")
        samples = _create_demo_samples()
    else:
        logger.info(f"从 {args.file} 加载评估数据...")
        builder = DatasetBuilder()
        if args.format == "jsonl":
            builder.build_from_jsonl(args.file)
        else:
            builder.build_from_csv(args.file)
        samples = builder.build()

    # 保存数据集（如果指定了路径）
    if args.save_dataset:
        save_evaluation_dataset(samples, args.save_dataset)
        logger.info(f"数据集已保存到 {args.save_dataset}")

    # 执行评估
    logger.info("开始 Ragas 风格评估...")
    evaluator = RAGEvaluator(
        include_ground_truth=args.with_gt,
        model=args.model,
        max_concurrency=args.max_concurrency,
    )
    report = await evaluator.evaluate(samples)

    # 输出结果
    RAGEvaluator.print_report(report)

    # 保存报告（如果指定了路径）
    if args.output:
        RAGEvaluator.save_report(report, args.output)
        logger.info(f"报告已保存到 {args.output}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
