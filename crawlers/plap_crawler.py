"""军队采购网爬虫.

支持栏目:
- 采购公告: https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html
"""
import time
from urllib.parse import urljoin, parse_qs, urlparse

from loguru import logger
import requests
from bs4 import BeautifulSoup, Comment

import util
from crawlers.crawler import Crawler
from dao import NoticeDao
from models import NoticeDto, SiteDto

DEFAULT_HEADERS = {
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

BASE_URL = "https://www.plap.mil.cn"
LIST_API = (
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

# 公告类型映射（工程类）
NOTICE_TYPE_MAP = {
    "001011": "招标公告",
    "001013": "竞争性谈判公告",
    "001014": "询价公告",
    "001052": "资格预审公告",
}

# 非招标公告类型（用于过滤）
EXCLUDED_NOTICE_TYPES = {
    "001021",  # 中标公示
    "001023",  # 采购结果公示
    "001024",  # 采购结果公示
    "001006",  # 废标公告
    "001031",  # 变更公告
    "59",  # 意向公开
    "00105E",  # 需求公示
    "001051",  # 单一来源公示
    "001068",  # 征集方案
    "001069",  # 征求意见 / 采购征求意见公告
    "001072",  # 采购公告（物资/服务）
    "001073",  # 成交公告
    "001076",  # 成交公示
    "001151",  # 单一来源公告
    "001201",  # 预先采购
    "001202",  # 新被装采购
}


class PLAPCrawler(Crawler):
    """军队采购网爬虫.

    仅抓取北京地区、项目类别为工程的公告信息。
    """

    PROMPT = """你是一个专业的军队采购网招标公告信息提取助手，你的任务是从给定的军队采购公告页HTML中，提取关键的招标信息。
需要提取的字段如下（字段名必须严格与下面列出的英文名称一致；如果文本中确实没有该信息，不要编造）：

- project_name: 采购项目名称
- project_no: 项目编号（如"2026-JLYJXT-G1001"）
- purchase_plan_no: 采购计划编号
- method: 采购方式（如"公开招标"、"竞争性谈判"、"询价"、"单一来源"）
- budget: 预算金额
- currency: 币种，默认为"CNY"
- joint_bid_allowed: 是否允许联合投标: 0-不允许 1-允许 整数类型，默认值：0
- join_bid_max_members: 联合投标最多参与方数量，整数类型，默认值：1
- sme_oriented: 是否专门面向中小企业: 0-不是 1-是，整数类型，默认值：0

- region_province: 采购方所在省份，如"北京"
- region_city: 采购方所在城市，如"北京"
- region_district: 采购方所在区/县（如"丰台区"、"海淀区"），从公告正文中提取

- notice_date: 公告发布时间，严格格式化为 YYYY-MM-DD HH:MM
- doc_obtain_start: 采购文件获取开始时间，格式 YYYY-MM-DD HH:MM
- doc_obtain_end: 采购文件获取截止时间，格式 YYYY-MM-DD HH:MM
- bid_deadline: 投标截止时间/响应文件提交截止时间，格式 YYYY-MM-DD HH:MM
- bid_open_time: 开标时间，格式 YYYY-MM-DD HH:MM

- bid_platform: 投标平台/开标地点
- doc_price: 招标文件费用

- purchaser_name: 采购人/招标人名称
- purchaser_address: 采购人地址
- purchaser_contact_person: 采购人联系人姓名
- purchaser_contact_phone: 采购人联系电话
- agency_name: 代理机构名称
- agency_address: 代理机构地址
- agency_contact_person: 代理机构联系人姓名
- agency_contact_phone: 代理机构联系电话
- project_contact_person: 项目联系人姓名
- project_contact_phone: 项目联系电话

- qualification_summary: 申请方/供应商资质要求摘要
- industry_tags: [
    "行业大类标签",
    "行业细分标签1"
] 所需供应商的行业标签（字符串列表类型）

- abstract: 公告内容摘要，500字以内
- supplier_profile: 所需供应商的画像，要包含：供应商需要在哪些行业、所需的资质/证书、供应商要具备能力等，300字以内

- notice_attachments: [
    {
        name: 附件名,
        url: 附件链接
    }
] 公告附件列表

- notice_packages: [
    {
        no: 采购包编号,
        name: 采购包名称,
        budget: 包预算(只能是数字),
        quantity: 采购数量(字符串类型，默认值是空字符串),
        unit: 货品单位(字符串类型，默认值是空字符串),
        intro: 标项规格描述或概况介绍
    }
] 采购包列表

- notice_qualifications: [
    {
        qualification_type: 资质类型,
        name: 资质/证书名称
    }
] 供应商/申请方资质要求列表

返回格式要求：
1. 只返回纯 JSON 对象，不要包含 markdown 代码块标记
2. 不要添加任何解释性文字
3. 所有字段名必须严格使用上面列出的英文名称
4. 字符串值保持原文，不要翻译或改写
5. 预算或费用金额统一换算成元，字符串格式，最多保留两位非0小数，如果都是0，不保留小数位
6. 对于日期，如果时间是24:00,请把它变成23:59

你要解析的公告页HTML内容如下：

"""

    def __init__(self, site: SiteDto):
        self.site = site
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    # ========================================================================
    # 第1步：fetch_list
    # ========================================================================
    def fetch_list(self, pages: int = 10) -> dict:
        job_name = self.site.job_name()
        latest = NoticeDao.get_latest(self.site.platform, self.site.part)
        all_notices = []
        html_saved = 0
        for page in range(1, pages + 1):
            url = self._build_list_url(page)
            notices = self._parse_list_page(url)

            all_notices.extend(notices)
            reach_latest = False
            if latest:
                for idx, notice in enumerate(all_notices):
                    if notice.url == latest.url:
                        all_notices = all_notices[:idx]
                        reach_latest = True
                        break
            logger.info(f"{job_name} 第{page}页 获取 {len(notices)} 条，累计 {len(all_notices)} 条")
            if reach_latest:
                break
            time.sleep(self.site.delay or 1)

        all_notices.reverse()
        tender_notices = [dto for dto in all_notices if self._is_tender_notice(dto)]
        excluded = len(all_notices) - len(tender_notices)
        if excluded > 0:
            logger.info(f"{job_name} 排除非招标公告 {excluded} 条，保留 {len(tender_notices)} 条")

        # 列表接口已返回 content，直接保存 HTML，状态设为 20（已获取 HTML）
        for dto in tender_notices:
            if dto.html:
                html_saved += 1
                dto.status = 20

        if tender_notices:
            NoticeDao.create(tender_notices)
            logger.info(f"{job_name} 入库完成: 新增 {len(tender_notices)} 条（含 HTML {html_saved} 条）")
            return {"created": len(tender_notices), "html_saved": html_saved}

        return {"created": 0, "html_saved": 0}

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
                html = self._get(notice.url)
                if html:
                    html_path = self.save_cleaned_html(html)
                    NoticeDao.update_html(notice.id, html_path)
                    success += 1
                    time.sleep(self.site.delay or 1)
                else:
                    failed += 1

            if len(notices) < limit:
                break

        logger.info(f"{job_name} 完成: 成功 {success} 条, 失败 {failed} 条")
        return {"updated": success}

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

    def _get(self, url: str) -> str | None:
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

    def _build_list_url(self, page: int) -> str:
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

        return LIST_API.format(
            base=BASE_URL,
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

    def _parse_list_page(self, list_url: str) -> list[NoticeDto]:
        """解析列表接口，返回招标公告 DTO 列表."""
        text = self._get(list_url)
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
            detail_url = urljoin(BASE_URL, pageurl)

            dto = NoticeDto(
                platform=self.site.platform,
                part=self.site.part,
                title=title,
                url=detail_url,
            )

            # 公告类型
            notice_type_code = item.get("noticeType", "")
            dto.notice_type = NOTICE_TYPE_MAP.get(notice_type_code, "")

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
    def _is_tender_notice(dto: NoticeDto) -> bool:
        """判断是否属于招标类公告."""
        # 根据公告类型快速判断
        if dto.notice_type:
            nt = dto.notice_type.strip()
            if any(k in nt for k in ("招标", "谈判", "询价", "资格预审")):
                # 进一步排除标题中的结果类/公示类公告
                exclude_keywords = (
                    "中标", "成交", "结果公示", "采购结果公示", "更正", "废标", "终止",
                    "意向公开", "需求公示", "征求意见"
                )
                if any(kw in dto.title for kw in exclude_keywords):
                    return False
                return True
            return False

        # notice_type 为空时，根据标题推断
        if "招标公告" in dto.title or "竞争性谈判" in dto.title or "询价公告" in dto.title:
            exclude_keywords = (
                "中标", "成交", "结果公示", "采购结果公示", "更正", "废标", "终止",
                "意向公开", "需求公示", "征求意见"
            )
            if any(kw in dto.title for kw in exclude_keywords):
                return False
            return True
        return False
