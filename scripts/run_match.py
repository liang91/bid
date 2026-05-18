#!/usr/bin/env python3
"""运行匹配引擎（粗筛 + 语义排序），输出候选结果.

用法:
    python scripts/run_match.py [--supplier 1001] [--top-k 200]

说明:
    为指定供应商或全部供应商执行匹配流程：
    1. SQL硬规则粗筛（地域/预算/采购方式/排除项/CA/中小企业）
    2. Embedding语义排序
    3. 输出排序后的候选列表（供后续AI精筛使用）
"""
import argparse
import json
import logging
import sys

sys.path.insert(0, ".")

from config import load_config
from match.match_engine import MatchEngine
from dao import SupplierProfileDao

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="运行匹配引擎")
    parser.add_argument("--supplier", type=int, default=0, help="指定供应商 id（0=全部）")
    parser.add_argument("--top-k", type=int, default=200, help="语义排序后保留的 Top K 条")
    parser.add_argument("--output", type=str, default="", help="结果输出到文件（JSON）")
    args = parser.parse_args()

    load_config()
    engine = MatchEngine()

    if args.supplier > 0:
        supplier = SupplierProfileDao.instance().get_by_id(args.supplier)
        if not supplier:
            logger.error(f"供应商 {args.supplier} 不存在")
            sys.exit(1)
        results = {args.supplier: engine.rank_for_supplier(supplier, top_k=args.top_k)}
    else:
        results = engine.batch_rank_for_all_suppliers(top_k=args.top_k)

    # 汇总统计
    total_candidates = sum(len(v) for v in results.values())
    logger.info(
        f"匹配完成: 共 {len(results)} 个供应商, 累计候选 {total_candidates} 条"
    )

    # 输出详细结果
    for supplier_id, scored in results.items():
        if not scored:
            continue
        logger.info(f"供应商 {supplier_id}: 候选 {len(scored)} 条, 最高分 {scored[0][0]:.4f}")

    # 可选：输出到文件
    if args.output:
        output_data = {}
        for supplier_id, scored in results.items():
            output_data[supplier_id] = [
                {
                    "score": round(score, 6),
                    "notice_id": notice.id,
                    "project_name": notice.project_name,
                    "category_name": notice.category_name,
                    "region_province": notice.region_province,
                    "budget": str(notice.budget) if notice.budget else "",
                }
                for score, notice in scored
            ]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
