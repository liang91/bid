"""数据访问对象包 —— SQLAlchemy 2.0 ORM 封装.

使用方式：
    from dao import ProcurementNoticeDao
    dao = ProcurementNoticeDao()
    dao.insert_list(notice_list)
"""
import logging

from config import config

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

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
    logger.fatal("init mysql failed")
else:
    logger.info("init mysql success")

db = sessionmaker(bind=engine)





# 导出各表 DAO 类
from dao.procurement_notice_dao import ProcurementNoticeDao  # noqa: E402
from dao.notice_attachment_dao import NoticeAttachmentDao  # noqa: E402
from dao.notice_package_dao import NoticePackageDao  # noqa: E402
from dao.notice_qualification_dao import NoticeQualificationDao  # noqa: E402
from dao.supplier_profile_dao import SupplierProfileDao  # noqa: E402
from dao.supplier_service_region_dao import SupplierServiceRegionDao  # noqa: E402
