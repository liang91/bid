from models import LatestUrlDto
from dao import LatestUrlDao


def test_creat():
    dto = LatestUrlDto(
        platform="platform1",
        part="part1",
        url="www.cctv.com"
    )
    id = LatestUrlDao.create(dto)
    print(id)


def test_get():
    dto = LatestUrlDao.get(platform="platform1", part="part1")
    print(dto.model_dump_json())

def test_update():
    dto = LatestUrlDao.get(platform="platform1", part="part1")
    dto.url = "www.mi.com"
    print(LatestUrlDao.update(dto))
