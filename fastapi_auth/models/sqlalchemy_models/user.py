import datetime
from typing import Type, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr
from typing_extensions import Optional

from fastapi_auth.models import token_model
from fastapi_auth.models.user import AbstractUser
from fastapi_auth.repositories.base import BaseUserRepository, BaseTokenRepository
from sqlalchemy import or_


class BaseUser(AbstractUser):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    password: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    time_created: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @declared_attr
    def token(cls) -> Mapped[token_model]:
        return relationship(back_populates="user")

    USERNAME_FIELD = ""

    async def save(self, **kwargs):
        session: AsyncSession = kwargs.get('session')
        if session is None:
            raise ValueError("Session cannot be None")
        return await session.commit()


class User(BaseUser):
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    USERNAME_FIELD = "username"


class EmailUser(BaseUser):
    email: Mapped[str] = mapped_column(String(128), nullable=False)

    USERNAME_FIELD = "email"


class UserRepository(BaseUserRepository[BaseUser]):
    def __init__(self, session: AsyncSession, user_model: Type[BaseUser], token_repo: BaseTokenRepository):
        self.session = session
        super().__init__(user_model, token_repo)

    async def get(self, **kwargs) -> Optional[BaseUser]:
        filters = [getattr(self.user_model, key) == value for key, value in kwargs.items()]
        query = select(self.user_model).filter(or_(*filters))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> BaseUser:
        password = kwargs.pop('password', None)
        user = self.user_model(**kwargs)
        if password is not None:
            user.set_password(kwargs.get(password))
        else:
            user.set_unusable_password()
        await user.save(session=self.session)
        await self.token_repo.create(user=user)
        await self.session.refresh(user)
        return user

    async def get_by_natural_key(self, natural_key: str) -> Optional[BaseUser]:
        query = select(self.user_model).filter(or_(**{self.user_model.USERNAME_FIELD: natural_key}))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
