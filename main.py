#!/usr/bin/env python3
"""项目主入口脚本.

支持功能：
1. 爬虫：分步骤爬取政府采购网公告
2. 补算：为存量数据计算 Embedding 向量
3. 匹配：运行匹配引擎（粗筛 + 语义排序）

用法示例:
    # 爬虫
    python main.py --step list --pages 2
    python main.py --step html --limit 50
    python main.py --step parse --limit 20

    # 补算 Embedding
    python main.py --step backfill_notice --batch 50 --limit 100
    python main.py --step backfill_supplier

    # 匹配
    python main.py --step match --top-k 200
    python main.py --step match --supplier 1001 --output result.json
"""
import argparse
from services import ClawerService, MatchService, NoticeService


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="招标信息服务平台主入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例:
  # 爬虫
  python main.py --step list --pages 1
  python main.py --step html --limit 2
  python main.py --step parse --limit 2

  # 匹配
  python main.py --step match --top-k 200
  python main.py --step match --supplier 1001 --output result.json
        """,
    )

    parser.add_argument(
        "--step", type=str, required=True,
        choices=["list", "html", "parse", "backfill_notice", "backfill_supplier", "match"],
        help="执行步骤",
    )

    # 爬虫参数
    parser.add_argument(
        "--part", type=str, default="dfgg", choices=["dfgg", "zygg"],
        help="爬取栏目: dfgg=地方公告, zygg=中央公告",
    )

    # 共用参数
    parser.add_argument(
        "--size", type=int, default=100,
        help="每次处理的最大条数 (默认: 100)",
    )

    # 推荐的条数
    parser.add_argument(
        "--top-k", type=int, default=200,
        help="语义排序后保留的 Top K 条 (默认: 200，仅 match 有效)",
    )

    args = parser.parse_args()

    if args.step in ("list", "html"):
        ClawerService.run("dfgg", args.step, args.size)
    elif args.step == "match":
        MatchService.rank_for_supplier(args.supplier)
    elif args.step == "parse":
        print(NoticeService.parse_htmls(args.size))


if __name__ == "__main__":
    main()
