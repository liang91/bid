#!/usr/bin/env python3
"""项目主入口脚本.

支持功能：
1. 爬虫：分步骤爬取政府采购网公告
2. 补算：为存量数据计算 Embedding 向量
3. 匹配：运行匹配引擎（粗筛 + 语义排序）
4. 调度器：启动后台定时任务

用法示例:
    # CLI 模式（指定 target-id 从数据库读取配置）
    python main.py --step list --target-id 1
    python main.py --step list --target-id 1 --size 3

    # CLI 模式（兼容旧方式，直接指定 part）
    python main.py --step list --part dfgg --size 2
    python main.py --step html --part dfgg --size 50

    # 调度器模式
    python main.py --schedule
"""
import argparse
import signal
import sys
import time

from loguru import logger
from services import CrawlerService, NoticeService, SupplierService, ScheduleService
from dao import SiteDao


# ---------------------------------------------------------------------------
# CLI 模式
# ---------------------------------------------------------------------------
def run_cli(args):
    if args.step in ("fetch-list", "fetch-html"):
        site = SiteDao.get(args.site)
        if not site:
            logger.error(f"[CLI] target_id={args.site} 不存在")
            sys.exit(1)
        CrawlerService.run(site)
    elif args.step == "match":
        SupplierService.filtered_notices(args.supplier)
    elif args.step == "parse":
        NoticeService.parse_htmls(args.size)
        logger.info("parse htmls done")


# ---------------------------------------------------------------------------
# 调度器模式
# ---------------------------------------------------------------------------
def run_scheduler():
    ScheduleService.start()

    def shutdown_handler(signum, frame):
        logger.info("[Scheduler] 收到退出信号，正在关闭...")
        ScheduleService.shutdown()
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
  # CLI 模式（指定 site-id）
  python main.py --step fetch-list --site 1
  python main.py --step fetch-html --site 1

  # CLI 模式（兼容旧方式）
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
        choices=["fetch-list", "fetch-html"],
        help="执行步骤（CLI 模式必填）",
    )

    parser.add_argument(
        "--site", type=int, default=0,
        help="爬虫目标配置 ID（从 sites 表读取）",
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
