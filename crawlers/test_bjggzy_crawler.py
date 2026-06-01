from dao import SiteDao
from crawlers import BJGGZYCrawler


def test_crawl():
    site = SiteDao.get(6)
    BJGGZYCrawler(site).fetch_list()
