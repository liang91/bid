from dao import SiteDao
from crawlers import CCGPCrawler


class TestCcgpCrawler:
    def test_fetch_list(self):
        site = SiteDao.get(1)
        ccgp_crawler = CCGPCrawler(site)
        res = ccgp_crawler.fetch_list(1)
        print(res)


