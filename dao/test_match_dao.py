from dao import MatchDao
from models import MatchDto, MatchedNotice

class TestMatchDao:
    def test_create(self):
        dto = MatchDto(
            supplier_id=37,
            filtered_notices=[
                MatchedNotice(notice_id=89, score=0.591),
                MatchedNotice(notice_id=96, score=0.454),
            ],
            status=20
        )
        print(MatchDao.create(dto))

    def test_get(self):
        dto = MatchDao.get(2)
        print(dto.model_dump_json())

    def test_delete(self):
        print(MatchDao.delete(2))