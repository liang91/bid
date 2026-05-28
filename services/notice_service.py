from concurrent.futures.thread import ThreadPoolExecutor

from loguru import logger

import util
from crawlers import CCGPCrawler
from dao import NoticeDao, NoticeAttachmentDao, NoticePackageDao, NoticeQualificationDao
from models import NoticeAttachmentDto, NoticePackageDto, NoticeQualificationDto, NoticeDto
from providers import LLMParser, LLMEmbedding


class NoticeService:
    @staticmethod
    def parse_html(notice: NoticeDto) -> bool:
        if not notice.html:
            logger.warning(f"公告{notice.id}无HTML内容")
            return False

        try:
            data = LLMParser.parse(CCGPCrawler.PROMPT + util.get_html(notice.html))
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
            logger.error(f"公告{notice.id} HTML解析失败:", e)
            return False

    @staticmethod
    def parse_htmls(limit: int = 100):
        notices = NoticeDao.fetch_unparsed(limit)
        if not notices:
            logger.info("没有HTML需要解析")
        else:
            ThreadPoolExecutor(max_workers=100).map(NoticeService.parse_html, notices)
