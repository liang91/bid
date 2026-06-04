"""中国政府采购网爬虫实现."""
from urllib.parse import urljoin

from loguru import logger
from bs4 import BeautifulSoup, Comment

import util
from crawlers.crawler import Crawler
from models import NoticeDto, SiteDto


class CCGPCrawler(Crawler):
    """中国政府采购网爬虫.

    支持爬取的栏目:
    - 地方公告 (dfgg): https://www.ccgp.gov.cn/cggg/dfgg/
    - 中央公告 (zygg): https://www.ccgp.gov.cn/cggg/zygg/
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    def __init__(self, site: SiteDto):
        super().__init__(site)
        self.session.headers.update(self.headers)

    def build_list_url(self, page: int) -> str:
        if page <= 1:
            return urljoin(self.site.url, "index.htm")
        return urljoin(self.site.url, f"index_{page}.htm")

    def parse_list_page(self, list_url: str) -> list[NoticeDto]:
        """解析列表页，返回招标公告 DTO 列表."""
        html = self.get(list_url)
        if html is None:
            return []

        notices = []
        soup = BeautifulSoup(html, "lxml")
        ul = soup.find("ul", class_="c_list_bid")
        if not ul:
            logger.warning(f"[解析] 未找到列表容器: {list_url}")
            return notices

        for li in ul.find_all("li"):
            a = li.find("a", href=True)
            if a is not None:
                dto = NoticeDto(
                    platform=self.site.platform,
                    part=self.site.part,
                    title=a["title"].strip(),
                    url=urljoin(list_url, a["href"]),
                )
                if em_type := li.find("em", attrs={"rel": "bxlx"}):
                    dto.notice_type = em_type.get_text(strip=True)
                notices.append(dto)
        return notices

    @staticmethod
    def save_cleaned_html(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        main = soup.find('div', class_='vF_deail_maincontent')
        # 去掉js/css代码
        for tag in main.find_all(['script', 'style']):
            tag.decompose()
        # 去掉评论
        for comment in main.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        # 去掉标签属性
        for tag in main.find_all():
            tag.attrs = {k: v for k, v in tag.attrs.items() if k == 'href'}
        content = str(main)
        content = content.replace("<span>", "").replace("</span>", "")
        return util.save_html(content)
