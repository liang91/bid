#!/usr/bin/env python3
"""项目主入口脚本.

支持功能：
1. 爬虫：分步骤爬取政府采购网公告
2. 补算：为存量数据计算 Embedding 向量
3. 匹配：运行匹配引擎（粗筛 + 语义排序）
4. 调度器：启动后台定时任务

用法示例:
    # CLI 模式
    python main.py --step list --pages 2
    python main.py --step html --limit 50
    python main.py --step parse --limit 20

    # 调度器模式
    python main.py --schedule
"""
import argparse
import signal
import sys
import time

from loguru import logger
from services import CrawlerService, NoticeService, SupplierService, ScheduleService


# ---------------------------------------------------------------------------
# CLI 模式
# ---------------------------------------------------------------------------
def run_cli(args):
    if args.step in ("list", "html"):
        CrawlerService.run("dfgg", args.step, args.size)
    elif args.step == "match":
        SupplierService.filtered_notices(args.supplier)
    elif args.step == "parse":
        NoticeService.parse_htmls(args.size)
        logger.info("parse htmls done")


# ---------------------------------------------------------------------------
# 调度器模式
# ---------------------------------------------------------------------------
def run_scheduler():
    scheduler = ScheduleService()
    scheduler.start()

    def shutdown_handler(signum, frame):
        logger.info("[Scheduler] 收到退出信号，正在关闭...")
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("[Scheduler] 调度器运行中，按 Ctrl+C 停止")
    while True:
        time.sleep(60)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="招标信息服务平台主入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例:
  # CLI 模式
  python main.py --step list --pages 1
  python main.py --step html --limit 2
  python main.py --step parse --limit 2
  python main.py --step match --supplier 37

  # 调度器模式
  python main.py --schedule
        """,
    )

    parser.add_argument(
        "--schedule", action="store_true",
        help="启动定时调度器（后台运行）",
    )

    parser.add_argument(
        "--step", type=str,
        choices=["list", "html", "parse", "match"],
        help="执行步骤（CLI 模式必填）",
    )

    parser.add_argument(
        "--part", type=str, default="dfgg", choices=["dfgg", "zygg"],
        help="爬取栏目: dfgg=地方公告, zygg=中央公告",
    )

    parser.add_argument(
        "--size", type=int, default=100,
        help="每次处理的最大条数 (默认: 100)",
    )

    parser.add_argument(
        "--top-k", type=int, default=200,
        help="语义排序后保留的 Top K 条 (默认: 200，仅 match 有效)",
    )

    parser.add_argument(
        "--supplier", type=int, default=0,
        help="供应商 ID（仅 match 有效）",
    )

    args = parser.parse_args()

    if args.schedule:
        run_scheduler()
    else:
        if not args.step:
            parser.error("--step is required when not in scheduler mode")
        run_cli(args)


if __name__ == "__main__":
    main()
