from concurrent.futures.thread import ThreadPoolExecutor

from loguru import logger

import util, os
from providers import OSS
from pathlib import Path
from dao import NoticeDao, NoticeAttachmentDao, NoticePackageDao, NoticeQualificationDao
from models import NoticeAttachmentDto, NoticePackageDto, NoticeQualificationDto, NoticeDto
from providers import LLMParser, LLMEmbedding


class NoticeService:
    PROMPT = """你是一个专业的公共资源交易平台招标公告信息提取助手，你的任务是从给定的招标公告页HTML中，提取关键的招标信息。
        需要提取的字段如下（字段名必须严格与下面列出的英文名称一致；如果文本中确实没有该信息，不要编造）：
        - notice_type: 公告类型 （枚举值，只能是后面这几种：公开招标、询价招标、资格预审、竞争性谈判、竞争性磋商、邀请招标、其他）
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
        - doc_obtain_start: 获取招标文件或资格预审文件开始时间，格式 YYYY-MM-DD HH:MM
        - doc_obtain_end: 获取招标文件或资格预审文件截止时间，格式 YYYY-MM-DD HH:MM
        - bid_deadline: 投标截止时间/响应文件提交/资格预审申请文件提交截止时间，格式 YYYY-MM-DD HH:MM
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
            "行业细分标签1",
            "行业细分标签2",
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
        6. 对于日期，如果时间是24:00,请把它变成23:59，如果日期为空设置值为null

        你要解析的公告页HTML内容如下：

        """
    @classmethod
    def parse_html(cls, notice: NoticeDto) -> bool:
        if not notice.html:
            logger.warning(f"公告{notice.id}无HTML内容")
            return False

        try:
            data = LLMParser.parse(cls.PROMPT + cls.get_html(notice.html))
            attachments = data.pop("notice_attachments", None) or []
            attachments = [NoticeAttachmentDto(**attachment) for attachment in attachments]

            packages = data.pop("notice_packages", None) or []
            packages = [NoticePackageDto(**package) for package in packages]

            qualifications = data.pop("notice_qualifications", None) or []
            qualifications = [NoticeQualificationDto(**qualification) for qualification in qualifications]

            notice_dict = notice.model_dump()
            notice_dict.update(data)
            notice = NoticeDto(**notice_dict)
            notice.supplier_profile_embedding = LLMEmbedding.embed(notice.supplier_profile)
            NoticeDao.update_parsed(notice)
            NoticeAttachmentDao.insert(notice.id, attachments)
            NoticePackageDao.insert(notice.id, packages)
            NoticeQualificationDao.insert(notice.id, qualifications)
            logger.info(f"公告{notice.id} HTML解析成功")
            return True
        except Exception as e:
            logger.error(f"公告{notice.id} HTML解析失败:{e}")
            return False

    @classmethod
    def parse_htmls(cls, limit: int = 100):
        notices = NoticeDao.fetch_unparsed(limit)
        if not notices:
            logger.info("没有HTML需要解析")
            return 0
        with ThreadPoolExecutor(max_workers=100) as executor:
            for notice in notices:
                executor.submit(NoticeService.parse_html, notice)
        return len(notices)

    @classmethod
    def get_html(cls, key: str) -> str:
        filepath = os.path.join(util.project_dir, key)
        if not Path(filepath).exists():
            OSS.get(key, filepath)
        return Path(filepath).read_text(encoding="utf-8")
