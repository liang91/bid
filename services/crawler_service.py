from loguru import logger
from crawlers import CCGPCrawler


class ClawerService:

    @staticmethod
    def run(part: str, step: str, size: int):
        crawler = CCGPCrawler(part)

        if step == "list":
            logger.info(">>> 执行第1步: fetch_list (爬取列表页，保存概要信息)")
            result = crawler.fetch_list(pages=size)
            logger.info(f"[结果] 爬取 {result['crawled']} 条, 入库 {result['inserted']} 条")
        elif step == "html":
            logger.info(">>> 执行第2步: fetch_html (获取详情页 HTML，status=1 → 20)")
            result = crawler.fetch_html(limit=size)
            logger.info(f"[结果] 共 {result['total']} 条, 成功 {result['success']} 条, 失败 {result['failed']} 条")
        elif step == "parse":
            logger.info(">>> 执行第3步: parse_detail (LLM 解析详情，status=20 → 30)")
            result = crawler.parse_detail(limit=size)
            logger.info(f"[结果] 共 {result['total']} 条, 成功 {result['success']} 条, 失败 {result['failed']} 条")
