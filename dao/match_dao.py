from dao import db
from models import MatchDto, Match
from sqlalchemy import delete, select, update


class MatchDao:
    @staticmethod
    def get(match_id: int) -> MatchDto | None:
        with db() as session:
            obj = session.get(Match, match_id)
            if not obj:
                return None
            return MatchDto.model_validate(obj)

    @staticmethod
    def create(dto: MatchDto) -> int:
        with db.begin() as session:
            match = Match(**dto.model_dump(exclude={"id", "created_at", "updated_at"}))
            session.add(match)
            session.flush()
            return match.id

    @staticmethod
    def delete(match_id: int) -> bool:
        with db.begin() as session:
            stmt = delete(Match).where(Match.id == match_id)
            res = session.execute(stmt)
            return res.rowcount == 1

    @staticmethod
    def fetch_by_status(status: int, limit: int = 100) -> list[MatchDto]:
        """按状态查询匹配记录."""
        with db() as session:
            stmt = select(Match).where(Match.status == status).order_by(Match.id.asc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [MatchDto.model_validate(row) for row in rows]

    @staticmethod
    def update(dto: MatchDto) -> bool:
        """更新匹配记录."""
        if not dto.id:
            return False
        with db.begin() as session:
            stmt = update(Match).where(Match.id == dto.id).values(
                dto.model_dump(exclude={"id", "created_at"})
            )
            res = session.execute(stmt)
            return res.rowcount == 1

