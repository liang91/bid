"""数据访问对象包 —— SQLAlchemy 2.0 ORM 封装.

使用方式：
    from dao import NoticeDao
    dao = NoticeDao()
    dao.insert_list(notice_list)
"""
from loguru import logger

from config import config

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

url = ("mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset={charset}".format(
    user=config.get("mysql.user"),
    password=config.get("mysql.password"),
    host=config.get("mysql.host"),
    port=config.get("mysql.port"),
    database=config.get("mysql.database"),
    charset=config.get("mysql.charset"),
))

engine = create_engine(url)

if engine is None:
    logger.error("init mysql failed")
else:
    logger.info("init mysql success")

db = sessionmaker(bind=engine)


def orm_to_dto(orm_obj, dto_cls):
    """将 SQLAlchemy ORM 对象转换为 Pydantic DTO 对象."""
    kwargs = {}
    for name, info in dto_cls.model_fields.items():
        val = getattr(orm_obj, name, None)
        if val is None:
            if info.default is not None:
                val = info.default
            elif info.default_factory is not None:
                val = info.default_factory()
        kwargs[name] = val
    return dto_cls.model_construct(**kwargs)


# 导出各表 DAO 类
from dao.notice_dao import NoticeDao
from dao.notice_attachment_dao import NoticeAttachmentDao
from dao.notice_package_dao import NoticePackageDao
from dao.notice_qualification_dao import NoticeQualificationDao
from dao.supplier_dao import SupplierDao
from dao.supplier_service_region_dao import SupplierServiceRegionDao
from dao.match_dao import MatchDao
from dao.job_log_dao import JobLogDao
from dao.site_dao import SiteDao
