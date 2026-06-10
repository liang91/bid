"""users 表的数据访问对象."""

from datetime import datetime

from sqlalchemy import select, update

from dao import db
from models import User, UserDto


class UserDao:
    """供应商人员存储器."""

    @staticmethod
    def create(dto: UserDto) -> int:
        with db.begin() as session:
            user = User(**dto.model_dump())
            session.add(user)
            session.flush()
            return user.id

    @staticmethod
    def get_by_uid(user_id: int) -> UserDto | None:
        """根据 user_id（业务字段）查询人员."""
        with db() as session:
            stmt = select(User).where(User.user_id == user_id)
            obj = session.execute(stmt).scalar_one_or_none()
            if not obj:
                return None
            return UserDto.model_validate(obj)

    @staticmethod
    def get_by_oid(openid: str) -> UserDto | None:
        """根据小程序openid查询人员."""
        with db() as session:
            stmt = select(User).where(User.wx_openid == openid)
            obj = session.execute(stmt).scalar_one_or_none()
            if not obj:
                return None
            return UserDto.model_validate(obj)

    @staticmethod
    def create_with_id(dto: UserDto) -> int:
        """手动指定id创建用户（id由调用方生成，如时间戳）."""
        with db.begin() as session:
            user = User(**dto.model_dump())
            session.add(user)
            session.flush()
            return user.id

    @staticmethod
    def get_by_phone(phone: str) -> UserDto | None:
        """根据手机号查询人员."""
        with db() as session:
            stmt = select(User).where(User.phone == phone)
            obj = session.execute(stmt).scalar_one_or_none()
            if not obj:
                return None
            return UserDto.model_validate(obj)

    @staticmethod
    def get_by_external_userid(external_userid: str) -> UserDto | None:
        """根据企微外部联系人ID查询人员."""
        with db() as session:
            stmt = select(User).where(User.wechat_external_userid == external_userid)
            obj = session.execute(stmt).scalar_one_or_none()
            if not obj:
                return None
            return UserDto.model_validate(obj)

    @staticmethod
    def get_wechat_bound_users(supplier_id: int) -> list[UserDto]:
        """查询某供应商下已绑定企微且正常状态的人员."""
        with db() as session:
            stmt = (select(User)
                    .where(User.supplier_id == supplier_id)
                    .where(User.status == 1)
                    .where(User.wechat_external_userid != "")
                    .where(User.wechat_follower_id != "")
                    .order_by(User.id.asc())
                    )
            rows = session.execute(stmt).scalars().all()
            return [UserDto.model_validate(row) for row in rows]

    @staticmethod
    def bind_wechat(user_id: int, external_userid: str, follow_user_id: str, state: str = "" ) -> bool:
        """更新人员的企微绑定信息."""
        with db.begin() as session:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(
                    wechat_external_userid=external_userid,
                    wechat_follow_user_id=follow_user_id,
                    wechat_bind_state=state,
                    wechat_bind_time=datetime.now(),
                )
            )
            res = session.execute(stmt)
            return res.rowcount == 1

    @staticmethod
    def update(dto: UserDto) -> bool:
        """全量更新人员信息."""
        if not dto.id:
            return False
        with db.begin() as session:
            stmt = (
                update(User)
                .where(User.id == dto.id)
                .values(dto.model_dump(exclude={"id", "created_at"}))
            )
            res = session.execute(stmt)
            return res.rowcount == 1
