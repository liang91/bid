#!/usr/bin/env python3
"""中国政府采购网爬虫入口脚本.

用法示例:
    # 爬取地方公告前2页（仅列表信息）
    python run_crawler.py --pages 2

    # 爬取中央公告前1页，并获取详情
    python run_crawler.py --column zygg --pages 1 --detail

    # 按地域和关键词过滤
    python run_crawler.py --pages 5 --region 北京 --keyword 信息化

    # 使用 LLM 解析详情页（替代传统 HTML 解析）
    python run_crawler.py --pages 2 --detail --llm

    # 使用 LLM 解析，并指定其他模型
    python run_crawler.py --pages 2 --detail --llm --llm-model doubao-seed-2-0-lite-260215
"""
import argparse
import sys

from crawlers.ccgp import CCGPCrawler


def main():
    parser = argparse.ArgumentParser(
        description="中国政府采购网招标信息爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_crawler.py --pages 2
  python run_crawler.py --column zygg --pages 1 --detail
  python run_crawler.py --pages 5 --region 辽宁 --keyword 环保 --detail
  python run_crawler.py --pages 2 --detail --llm
        """,
    )
    parser.add_argument(
        "--column",
        type=str,
        default="zygg",
        choices=["dfgg", "zygg"],
        help="爬取栏目: dfgg=地方公告, zygg=中央公告 (默认: dfgg)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="爬取页数 (默认: 1, 设为0则爬取全部)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="是否爬取详情页（会大幅增加请求量和耗时）",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="使用 LLM（豆包模型）解析详情页，替代传统的 HTML 解析",
    )
    parser.add_argument(
        "--llm-api-key",
        type=str,
        default="791b346d-6956-432d-a3f2-1d206edbd7f1",
        help="豆包/火山引擎 API Key",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="doubao-seed-2-0-lite-260215",
        help="LLM 模型名称",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="按地域过滤，如: 北京、辽宁、江苏",
    )
    parser.add_argument(
        "--type",
        type=str,
        default=None,
        dest="notice_type",
        help="按公告类型过滤，如: 公开招标、中标公告、竞争性磋商",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="按标题关键词过滤",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="请求间隔秒数 (默认: 1.0)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data",
        help="输出目录 (默认: data)",
    )

    # 数据库连接参数
    parser.add_argument(
        "--db-host",
        type=str,
        default="localhost",
        help="MySQL 主机 (默认: localhost)",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=3306,
        help="MySQL 端口 (默认: 3306)",
    )
    parser.add_argument(
        "--db-user",
        type=str,
        default="root",
        help="MySQL 用户名 (默认: root)",
    )
    parser.add_argument(
        "--db-password",
        type=str,
        default="",
        help="MySQL 密码",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default="bid",
        help="MySQL 数据库名 (默认: bid)",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="禁用数据库写入，仅爬取不存储",
    )

    args = parser.parse_args()

    # pages=0 表示爬取全部
    pages = None if args.pages == 0 else args.pages

    from crawlers.llm_parser import LLMParser

    llm_parser = None
    if args.llm:
        llm_parser = LLMParser(
            api_key=args.llm_api_key,
            model=args.llm_model,
        )
        print(f"[LLM] 已启用 LLM 解析，模型: {args.llm_model}")

    # 初始化数据库存储
    db_storage = None
    if not args.no_db:
        from crawlers.db_storage import MySQLStorage
        db_storage = MySQLStorage(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            password=args.db_password,
            database=args.db_name,
        )
        print(f"[数据库] 已连接到 {args.db_host}:{args.db_port}/{args.db_name}")

    crawler = CCGPCrawler(
        column=args.column,
        delay=args.delay,
        storage=__import__("crawlers.storage", fromlist=["Storage"]).Storage(args.output),
        llm_parser=llm_parser,
        db_storage=db_storage,
    )

    crawler.run(
        pages=pages,
        fetch_detail=args.detail,
        use_llm=args.llm,
        region=args.region,
        notice_type=args.notice_type,
        keyword=args.keyword,
    )


if __name__ == "__main__":
    main()
