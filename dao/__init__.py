"""数据访问对象包 —— 负责 MySQL 数据库的初始化与 CRUD 操作.

使用方式：
    from dao import ProcurementNoticeDao
    ProcurementNoticeDao.instance().insert_list(notice_list)
"""
import logging

from pymysql.cursors import DictCursor

from .base import get_db_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 统一初始化数据库连接参数（包级别单例）
# ---------------------------------------------------------------------------

try:
    _cfg = get_db_config()
except FileNotFoundError:
    _cfg = {}
    logger.warning("配置文件不存在，使用默认数据库连接参数")

_CONN_PARAMS = {
    "host": _cfg.get("mysql.host") or "localhost",
    "port": _cfg.get("mysql.port", 3306),
    "user": _cfg.get("mysql.user") or "root",
    "password": _cfg.get("mysql.password", ""),
    "database": _cfg.get("mysql.database") or "bid",
    "charset": _cfg.get("mysql.charset") or "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": False,
}

# ---------------------------------------------------------------------------
# 导出各表 DAO 类（由基类 BaseStorage.instance 统一管理单例）
# ---------------------------------------------------------------------------

from .procurement_notice_dao import ProcurementNoticeDao  # noqa: E402
from .notice_attachment_dao import NoticeAttachmentDao  # noqa: E402
from .notice_package_dao import NoticePackageDao  # noqa: E402
from .notice_qualification_dao import NoticeQualificationDao  # noqa: E402

__all__ = [
    "ProcurementNoticeDao",
    "NoticeAttachmentDao",
    "NoticePackageDao",
    "NoticeQualificationDao",
]
