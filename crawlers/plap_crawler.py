"""军队采购网爬虫.

支持栏目:
- 采购公告: https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html
"""
from urllib.parse import urljoin, parse_qs, urlparse

from loguru import logger
import requests
from bs4 import BeautifulSoup, Comment

import util
from crawlers.crawler import Crawler
from models import NoticeDto, SiteDto


class PLAPCrawler(Crawler):
    """军队采购网爬虫.

    仅抓取北京地区、项目类别为工程的公告信息。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
    }

    base_url = "https://www.plap.mil.cn"

    list_api = (
        "{base}/freecms/rest/v1/notice/selectInfoMoreChannel.do"
        "?siteId={site_id}"
        "&channel={channel}"
        "&currPage={page}"
        "&pageSize={page_size}"
        "&noticeType={notice_type}"
        "&regionCode={region_code}"
        "&purchaseManner={purchase_manner}"
        "&title={title}"
        "&openTenderCode={open_tender_code}"
        "&operationStartTime={operation_start_time}"
        "&operationEndTime={operation_end_time}"
        "&selectTimeName={select_time_name}"
        "&cityOrArea={city_or_area}"
        "&purchaseNature={purchase_nature}"
        "&punishType={punish_type}"
    )

    def __init__(self, site: SiteDto):
        super().__init__(site)
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def build_list_url(self, page: int) -> str:
        # 从 site.url 解析 site_id 和 channel，若解析失败则使用默认值
        site_id = "404bb030-5be9-4070-85bd-c94b1473e8de"
        channel = "c5bff13f-21ca-4dac-b158-cb40accd3035"
        # 尝试从 url 参数中提取
        if self.site.url:
            parsed = urlparse(self.site.url)
            qs = parse_qs(parsed.query)
            if "siteId" in qs:
                site_id = qs["siteId"][0]
            if "channel" in qs:
                channel = qs["channel"][0]

        return self.list_api.format(
            base=self.base_url,
            site_id=site_id,
            channel=channel,
            page=page,
            page_size=20,
            notice_type="",
            region_code="110000",  # 北京地区
            purchase_manner="",
            title="",
            open_tender_code="",
            operation_start_time="",
            operation_end_time="",
            select_time_name="",
            city_or_area="",
            purchase_nature="2",  # 工程类
            punish_type="",
        )

    def parse_list_page(self, list_url: str) -> list[NoticeDto]:
        """解析列表接口，返回招标公告 DTO 列表."""
        text = self.get(list_url)
        if text is None:
            return []

        try:
            import json
            data = json.loads(text)
        except Exception as e:
            logger.warning(f"[解析] JSON 解析失败: {list_url} - {e}")
            return []

        notices = []
        rows = data.get("data", []) if isinstance(data, dict) else []
        for item in rows:
            pageurl = item.get("pageurl", "").strip()
            title = item.get("title", "").strip()
            if not pageurl or not title:
                continue

            # 拼接完整 URL
            detail_url = urljoin(self.base_url, pageurl)

            dto = NoticeDto(
                platform=self.site.platform,
                part=self.site.part,
                title=title,
                url=detail_url,
            )

            # 地区
            dto.region_province = "北京"
            dto.region_city = "北京"
            dto.region_district = item.get("regionName", "")

            # 项目编号
            dto.project_no = item.get("openTenderCode", "")

            # 发布时间
            notice_time = item.get("noticeTime", "")
            if notice_time:
                from datetime import datetime
                try:
                    dto.notice_date = datetime.strptime(notice_time, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            # 预算金额
            budget_str = item.get("budget", "")
            if budget_str:
                try:
                    from decimal import Decimal
                    dto.budget = Decimal(str(budget_str))
                except Exception:
                    pass

            # 列表接口直接返回详情页 content，保存为 HTML
            content_html = item.get("content", "")
            if content_html:
                dto.html = self.save_cleaned_html(content_html)

            notices.append(dto)
        return notices

    @staticmethod
    def save_cleaned_html(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        # 优先取 print_part（正文区域）
        main = soup.find("div", id="print_part")
        if not main:
            main = soup.find("div", class_="wrap_content_detail")
        if not main:
            main = soup.find("body")

        # 去掉 js/css 代码
        for tag in main.find_all(["script", "style"]):
            tag.decompose()
        # 去掉评论
        for comment in main.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        # 去掉标签属性（保留 href/src）
        for tag in main.find_all():
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("href", "src")}
        content = str(main)
        content = content.replace("<span>", "").replace("</span>", "")
        return util.save_html(content)
