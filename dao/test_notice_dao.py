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

    def test_fetch_candidates(self):
        supplier = SupplierDao.get(37)
        candidates = NoticeDao.fetch_candidates(
            region_names=[],
            min_budget=supplier.min_budget,
            max_budget=supplier.max_budget,
            limit=5
        )
        adapter = TypeAdapter(list[NoticeDto])
        print(adapter.dump_json(candidates, ensure_ascii=False))
