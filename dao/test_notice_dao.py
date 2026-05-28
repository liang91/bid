from loguru import logger
from pydantic import TypeAdapter

from models import NoticeDto
from dao import NoticeDao, SupplierDao


class TestNoticeDao:
    def test_get(self):
        dto = NoticeDao.get(53)
        if not dto:
            print("not exists")
        else:
            print(dto.model_dump_json(ensure_ascii=False))

    def test_create(self):
        res = NoticeDao.create([
            NoticeDto(project_name='测试项目1', url='url1'),
            NoticeDto(project_name='测试项目2', url='url2'),
        ])
        print(res)

    def test_fetch_unparsed(self):
        res = NoticeDao.fetch_unparsed()
        print(res)

    def test_update_html(self):
        html = 'html/1779948678862156.html'
        id = 62
        logger.info(NoticeDao.update_html(id, html))

    def test_fetch_candidates(self):
        supplier = SupplierDao.get(37)
        candidates = NoticeDao.fetch_candidates(
            region_names=[],
            min_budget=supplier.min_budget,
            max_budget=supplier.max_budget
        )
        for candidate in candidates:
            candidate.supplier_profile_embedding = None
        adapter = TypeAdapter(list[NoticeDto])
        print(adapter.dump_json(candidates, ensure_ascii=False).decode('utf-8'))
