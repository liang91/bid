from services import NoticeService
from dao import NoticeDao

def test_parse_html():
    notice = NoticeDao.get(1039)
    NoticeService.parse_html(notice)

def test_parse_htmls():
    NoticeService.parse_htmls()
    print("done")
