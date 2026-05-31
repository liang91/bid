from dao import SiteDao
from crawlers import PLAPCrawler


class TestPlapCrawler:
    def test_fetch_list(self):
        site = SiteDao.get_by_part("军队采购网", "采购公告")
        if not site:
            print("未找到军队采购网配置，跳过测试")
            return
        crawler = PLAPCrawler(site)
        res = crawler.fetch_list(pages=1)
        print(res)

    def test_fetch_html(self):
        site = SiteDao.get_by_part("军队采购网", "采购公告")
        if not site:
            print("未找到军队采购网配置，跳过测试")
            return
        crawler = PLAPCrawler(site)
        res = crawler.fetch_html(limit=5)
        print(res)

    def test_init_crawler(self):
        module = __import__("crawlers", fromlist=["PLAPCrawler"])
        cls = getattr(module, "PLAPCrawler")
        print(cls)
