import os
import time

import requests
from loguru import logger

import util
from dao import LatestUrlDao, NoticeDao
from models import SiteDto, LatestUrlDto, NoticeDto
from providers import LLMParser, OSS


class Crawler:


    def __init__(self, site: SiteDto):
        self.site = site
        self.session = requests.Session()

    # ========================================================================
    # 第1步：fetch_list 解析列表页里包含的公告基本信息
    # ========================================================================
    def fetch_list(self, pages: int = 10) -> dict:
        job_name = self.site.job_name()
        latest = LatestUrlDao.get(self.site.platform, self.site.part)
        notices = []
        for page in range(1, pages + 1):
            url = self.build_list_url(page)
            page_notices = self.parse_list_page(url)
            urls = [notice.url for notice in notices]
            page_notices = [notice for notice in page_notices if notice.url not in urls]
            notices.extend(page_notices)
            reach_latest = False
            if latest:
                for idx, notice in enumerate(notices):
                    if notice.url == latest.url:
                        notices = notices[:idx]
                        reach_latest = True
                        break
            logger.info(f"{job_name} 第{page}页 获取 {len(page_notices)} 条，累计 {len(notices)} 条")
            if reach_latest:
                break
            time.sleep(1)

        notices.reverse()
        if not latest:
            latest = LatestUrlDto(platform=self.site.platform, part=self.site.part, url=notices[-1].url)
        elif len(notices) > 0:
            latest.url = notices[-1].url

        notices = self.filter_notice(notices)
        if notices:
            NoticeDao.create(notices)
        LatestUrlDao.save(latest)
        return {"created": len(notices)}

    # 对从公告页抓取的公告列表，过滤并保留工程类的项目
    @staticmethod
    def filter_notice(notices: list[NoticeDto]) -> list[NoticeDto]:
        if not notices:
            return []

        result: list[NoticeDto] = []
        batches = [notices[i:i+30] for i in range(0, len(notices), 30)]
        for batch in batches:
            rows: list[str] = []
            for idx, notice in enumerate(batch):
                rows.append(f"公告id：{idx} 公告标题：{notice.title} 地区：{notice.region_province}")
            content = "\n".join(rows)
            prompt = """你是一个招标公告信息解析助手，我给你一批公告的基础信息，你的任务是把公告解析成如下JSON对象并返回：
                [
                    {
                        "id": 公告id（整形）
                        "title": 公告标题
                        "notice_type": 公告类型 （枚举值，只能是后面这几种：公开招标、询价招标、资格预审、竞争性谈判、竞争性磋商、邀请招标、其他）
                        "region": 公告发布地区是否属于京津冀（0:不属于 1:属于）
                        "project": 是否是工程类型的公告（0:不是 1:是）  
                    }
                ]
                注意：只返回JSON数据
                公告基本信息如下：
                """
            conditions = LLMParser.parse(prompt + content)
            for condition in conditions:
                if condition['region'] == 1 and condition['project'] == 1 and '其他' not in condition['notice_type']:
                    batch[condition['id']].notice_type = condition['notice_type']
                    result.append(batch[condition['id']])
        return result

    # ========================================================================
    # 第2步：fetch_html
    # ========================================================================
    def fetch_html(self, limit: int = 100) -> dict:
        job_name = self.site.job_name()
        success = failed = 0
        while True:
            notices = NoticeDao.fetch_by_status(
                status=1, platform=self.site.platform, part=self.site.part, limit=limit
            )
            if not notices:
                logger.info(f"{job_name} 没有待获取 HTML 的记录")
                return {"updated": 0}

            logger.info(f"{job_name} 共 {len(notices)} 条待处理")

            for notice in notices:
                html = self.get(notice.url)
                if html:
                    html = self.clean_html(notice.url, html)
                    key = self.save_html(notice.id, html)
                    NoticeDao.update_html(notice.id, key)
                    success += 1
                    time.sleep(1)
                else:
                    failed += 1

            if len(notices) < limit:
                break

        logger.info(f"{job_name} 完成: 成功 {success} 条, 失败 {failed} 条")
        return {"updated": success}

    def get(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=30)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code == 200:
                    return resp.text
                logger.warning(f"[HTTP {resp.status_code}] {url}")
            except requests.RequestException as e:
                logger.warning(f"[请求失败] 第{attempt}次尝试: {url} - {e}")
        return None

    def build_list_url(self, page: int) -> str:
        pass

    def parse_list_page(self, url: str) -> list[NoticeDto]:
        pass

    def clean_html(self, url: str, html: str) -> str:
        pass

    @staticmethod
    def save_html(fd: int, html: str) -> str:
        if not fd:
            fd = int(time.time() * 1000000)
        object_key = f"html/{fd}.html"
        filepath = os.path.join(util.project_dir, object_key)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        OSS.put(filepath, object_key)
        return object_key
