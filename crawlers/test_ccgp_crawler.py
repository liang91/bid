from crawlers import CCGPCrawler


class TestCcgpCrawler:
    def test_fetch_list(self):
        ccgp_crawler = CCGPCrawler('dfgg')
        res = ccgp_crawler.fetch_list(10)
        print(res)
