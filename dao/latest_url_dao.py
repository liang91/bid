from models import LatestUrl, LatestUrlDto
from dao import db
from sqlalchemy import select, update


class LatestUrlDao:

    @staticmethod
    def save(dto: LatestUrlDto):
        if not dto.id:
            LatestUrlDao.create(dto)
        else:
            LatestUrlDao.update(dto)

    @staticmethod
    def create(data: LatestUrlDto) -> int:
        with db.begin() as session:
            row = LatestUrl(**data.model_dump())
            session.add(row)
            session.flush()
            return row.id

    @staticmethod
    def get(platform: str, part: str) -> LatestUrlDto | None:
        with db() as session:
            stmt = select(LatestUrl).where(LatestUrl.platform == platform, LatestUrl.part == part)
            row = session.execute(stmt).scalar()
            if row:
                return LatestUrlDto.model_validate(row)
            return None

    @staticmethod
    def update(data: LatestUrlDto) -> bool:
        with db.begin() as session:
            values = data.model_dump(exclude={"id", "created", "updated"})
            stmt = update(LatestUrl).where(LatestUrl.id == data.id).values(values)
            res = session.execute(stmt)
            return res.rowcount == 1
