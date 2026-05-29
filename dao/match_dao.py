from dao import db
from models import MatchDto, Match
from sqlalchemy import delete

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
