"""北京市公共资源交易服务平台爬虫.

支持栏目:
- 工程建设招标公告: https://ggzyfw.beijing.gov.cn/jyxxggjtbyqs/
- 政府采购招标公告: https://ggzyfw.beijing.gov.cn/jyxxcggg/
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

import util
from crawlers.crawler import Crawler
from models import NoticeDto, SiteDto


class _BJGGZYSSLAdapter(HTTPAdapter):
    """适配北京市公共资源交易平台不兼容的 TLS 配置."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        # 降级 cipher 以兼容服务器旧的椭圆曲线配置
        ctx.set_ciphers("AES256-SHA256:AES128-SHA256:AES256-SHA:AES128-SHA")
        ctx.check_hostname = False
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class BJGGZYCrawler(Crawler):
    """北京市公共资源交易服务平台爬虫.

    市级平台已聚合各区公告（如【昌平区】【通州区】），
    因此爬取市级栏目即可覆盖市+区两级信息。
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
        # 北京市公共资源交易平台 TLS 兼容处理
        self.session.mount("https://", _BJGGZYSSLAdapter())

    def build_list_url(self, page: int) -> str:
        if page <= 1:
            return urljoin(self.site.url, "index.html")
        return urljoin(self.site.url, f"index_{page}.html")

    def parse_list_page(self, list_url: str) -> list[NoticeDto]:
        """解析列表页，返回招标公告 DTO 列表."""
        html = self.get(list_url)
        if html is None:
            return []

        notices = []
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", class_="divtitlejy"):
            href = a.get("href", "").strip()
            title = a.get("title", "").strip()
            if not href or not title:
                continue

            dto = NoticeDto(
                platform=self.site.platform,
                part=self.site.part,
                title=title,
                url=urljoin(list_url, href),
                region_province='北京'
            )

            # 尝试从内部 <p> 标签提取区域和项目编号，如：【昌平区】[S110000A001042382003]
            if p_tag := a.find("p"):
                p_text = p_tag.get_text(strip=True)
                if "【" in p_text and "】" in p_text:
                    district = p_text[p_text.find("【") + 1: p_text.find("】")]
                    dto.region_district = district

            notices.append(dto)
        return notices

    def clean_html(self, url: str, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        main = soup.find("div", class_="div-article2")
        if not main:
            main = soup.find("div", class_="newsCon")
        if not main:
            main = soup.find("div", class_="div-content")
        if not main:
            # 兜底：取 body
            main = soup.find("body")

        # 去掉 js/css 代码
        for tag in main.find_all(["script", "style"]):
            tag.decompose()
        # 去掉评论
        for comment in main.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        # 去掉标签属性（保留 href）
        for tag in main.find_all():
            tag.attrs = {k: urljoin(url, v) for k, v in tag.attrs.items() if k == "href"}
        content = str(main)
        content = content.replace("<span>", "").replace("</span>", "")
        return content
