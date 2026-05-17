#!/usr/bin/env python3
"""中国政府采购网爬虫入口脚本.

支持分步骤执行爬取流程（方便调度与错误排查）：
    python run_crawler.py --step list       # 第1步：爬取列表页，保存概要信息
    python run_crawler.py --step html       # 第2步：获取详情页 HTML
    python run_crawler.py --step parse      # 第3步：LLM 解析详情内容


用法示例:
    # 只爬取2页列表
    python run_crawler.py --step list --pages 2

    # 获取详情页 HTML（每次默认处理100条）
    python run_crawler.py --step html --limit 50

    # 解析详情（使用 LLM）
    python run_crawler.py --step parse --limit 20

"""
import argparse
import sys

from crawlers.ccgp import CCGPCrawler
from crawlers.config_loader import load_config


def main():
    parser = argparse.ArgumentParser(
        description="中国政府采购网招标信息爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
配置说明:
  所有数据库连接、LLM API 密钥等配置信息均从项目根目录 config.yaml 读取。

分步执行示例:
  python run_crawler.py --step list --pages 1
  python run_crawler.py --step html --limit 2
  python run_crawler.py --step parse --limit 2

        """,
    )

    # 步骤控制（核心参数）
    parser.add_argument(
        "--step",
        type=str,
        required=True,
        choices=["list", "html", "parse"],
        help="执行步骤: list=爬列表, html=获取详情HTML, parse=LLM解析",
    )

    # 运行时控制参数
    parser.add_argument(
        "--part",
        type=str,
        default="dfgg",
        choices=["dfgg", "zygg"],
        help="爬取栏目: dfgg=地方公告, zygg=中央公告",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="爬取页数 (默认: 1, 设为0则爬取全部，仅 --step list 有效)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="每次处理的最大条数 (默认: 100，仅 --step html/parse 有效)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="请求间隔秒数 (默认: 1.0)",
    )

    args = parser.parse_args()

    # 加载配置文件（固定路径：项目根目录 config.yaml）
    try:
        load_config()
        print("[配置] 已加载配置文件")
    except FileNotFoundError as e:
        print(f"[配置] 警告: {e}")

    # pages=0 表示爬取全部
    pages = None if args.pages == 0 else args.pages

    # 初始化 LLM 解析器（parse 步骤必须）
    llm_parser = None
    if args.step == "parse":
        from crawlers.llm_parser import LLMParser
        try:
            llm_parser = LLMParser()
            print(f"[LLM] 已启用 LLM 解析，模型: {llm_parser.model}")
        except ValueError as e:
            print(f"[LLM] 初始化失败: {e}")
            sys.exit(1)

    # 初始化数据库存储
    from crawlers.db_storage import MySQLStorage
    try:
        db_storage = MySQLStorage()
        print(
            f"[数据库] 已连接到 "
            f"{db_storage.conn_params['host']}:{db_storage.conn_params['port']}/"
            f"{db_storage.conn_params['database']}"
        )
    except Exception as e:
        print(f"[数据库] 连接失败: {e}")
        sys.exit(1)

    crawler = CCGPCrawler(
        part=args.part,
        delay=args.delay,
        llm_parser=llm_parser,
        db_storage=db_storage,
    )

    # 根据步骤执行
    if args.step == "list":
        print(f"\n>>> 执行第1步: fetch_list (爬取列表页，保存概要信息)\n")
        result = crawler.fetch_list(pages=pages)
        print(f"\n[结果] 爬取 {result['crawled']} 条, 过滤后 {result['filtered']} 条, 入库 {result['inserted']} 条")

    elif args.step == "html":
        print(f"\n>>> 执行第2步: fetch_html (获取详情页 HTML，status=1 → 20)\n")
        result = crawler.fetch_html(limit=args.limit)
        print(f"\n[结果] 共 {result['total']} 条, 成功 {result['success']} 条, 失败 {result['failed']} 条")

    elif args.step == "parse":
        print(f"\n>>> 执行第3步: parse_detail (LLM 解析详情，status=20 → 30)\n")
        result = crawler.parse_detail(limit=args.limit)
        print(f"\n[结果] 共 {result['total']} 条, 成功 {result['success']} 条, 失败 {result['failed']} 条")


if __name__ == "__main__":
    main()
