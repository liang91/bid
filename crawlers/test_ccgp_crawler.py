from dao import SiteDao
import importlib


class TestCcgpCrawler:
    # def test_fetch_list(self):
    #     site = SiteDao.get_by_part("中国政府采购网", 'dfgg')
    #     ccgp_crawler = CCGPCrawler(site)
    #     res = ccgp_crawler.fetch_list(10)
    #     print(res)

    def test_init_crawler(self):
        module = importlib.import_module("crawlers")  # 1. 动态导入包（无需精确到模块，__init__.py 已导出所有爬虫类）
        cls = getattr(module, "CCGPCrawler")  # 2. 从模块中反射获取类
        site = SiteDao.get_by_part("中国政府采购网", 'dfgg')  # 3. 实例化
        crawler = cls(site)
        print(crawler)
