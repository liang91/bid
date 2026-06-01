"""crawl_targets 表的数据访问对象."""

from sqlalchemy import select, update

from models import Site, SiteDto
from dao import db


class SiteDao:
    """爬虫目标配置存储器."""

    @staticmethod
    def get(site_id: int) -> SiteDto | None:
        """根据ID查询目标配置."""
        with db() as session:
            obj = session.get(Site, site_id)
            if not obj:
                return None
            return SiteDto.model_validate(obj)

    @staticmethod
    def get_by_part(platform: str, part: str) -> SiteDto | None:
        """根据网站代码和栏目代码查询."""
        with db() as session:
            stmt = select(Site).where(Site.platform == platform, Site.part == part).limit(1)
            row = session.execute(stmt).scalar()
            if row:
                return SiteDto.model_validate(row)
            return None

    @staticmethod
    def all() -> list[SiteDto]:
        """查询所有目标配置."""
        with db() as session:
            stmt = select(Site)
            rows = session.execute(stmt).scalars().all()
            return [SiteDto.model_validate(row) for row in rows]

    @staticmethod
    def enabled() -> list[SiteDto]:
        """查询所有启用的目标配置."""
        with db() as session:
            stmt = select(Site).where(Site.enabled == 1)
            rows = session.execute(stmt).scalars().all()
            return [SiteDto.model_validate(row) for row in rows]

    @staticmethod
    def create(dto: SiteDto) -> int:
        """新增目标配置."""
        with db.begin() as session:
            obj = Site(**dto.model_dump(exclude={"id", "created_at", "updated_at"}))
            session.add(obj)
            session.flush()
            return obj.id

    @staticmethod
    def update(site_id: int, **kwargs) -> bool:
        """更新目标配置."""
        with db.begin() as session:
            stmt = update(Site).where(Site.id == site_id).values(**kwargs)
            res = session.execute(stmt)
            return res.rowcount == 1

    @staticmethod
    def delete(site_id: int) -> bool:
        """删除目标配置."""
        with db.begin() as session:
            obj = session.get(Site, site_id)
            if obj:
                session.delete(obj)
                return True
            return False
