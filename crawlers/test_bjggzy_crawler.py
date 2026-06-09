from dao import SiteDao
from crawlers import BJGGZYCrawler


def test_fetch_list():
    site = SiteDao.get(6)
    BJGGZYCrawler(site).fetch_list(5)

def test_fetch_html():
    site = SiteDao.get(9)
    BJGGZYCrawler(site).fetch_html(1)