import time

import requests
from loguru import logger

from dao import LatestUrlDao, NoticeDao
from models import SiteDto, LatestUrlDto, NoticeDto
from providers import LLMParser


class Crawler:
    PROMPT = """你是一个专业的公共资源交易平台招标公告信息提取助手，你的任务是从给定的招标公告页HTML中，提取关键的招标信息。
    需要提取的字段如下（字段名必须严格与下面列出的英文名称一致；如果文本中确实没有该信息，不要编造）：

    - project_name: 采购项目名称
    - project_no: 项目编号
    - purchase_plan_no: 采购计划编号
    - method: 采购方式（如"公开招标"、"竞争性谈判"、"询价"、"单一来源"）
    - budget: 预算金额
    - currency: 币种，默认为"CNY"
    - joint_bid_allowed: 是否允许联合投标: 0-不允许 1-允许 整数类型，默认值：0
    - join_bid_max_members: 联合投标最多参与方数量，整数类型，默认值：1
    - sme_oriented: 是否专门面向中小企业: 0-不是 1-是，整数类型，默认值：0

    - region_province: 采购方所在省份，固定为"北京"
    - region_city: 采购方所在城市，固定为"北京"
    - region_district: 采购方所在区/县（如"昌平区"、"通州区"），从公告正文中提取

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
        else:
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
        batches = [notices[i:i+50] for i in range(0, len(notices), 50)]
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
                    html_path = self.save_cleaned_html(html)
                    NoticeDao.update_html(notice.id, html_path)
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
