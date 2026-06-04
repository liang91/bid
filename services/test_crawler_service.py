from dao import SiteDao
from services import CrawlerService


class TestCrawlerService:
    def test_get_crawler(self):
        site = SiteDao.get_by_part('中国政府采购网', '地方公告')
        crawler = CrawlerService.get_crawler(site)
        crawler.fetch_list(2)
