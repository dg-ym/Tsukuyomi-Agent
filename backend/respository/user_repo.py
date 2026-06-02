from models import AsyncSession
from models.user import EmailCode
from sqlalchemy import select, exists,update
from datetime import datetime, timedelta
from models.user import User, password_hash
from schemas.user import UserCreateSchema, UserResetSchema


class UserRepository:
    def __init__(self,session: AsyncSession):
        self.session = session

    async def get_by_email(self,email: str) -> User | None:
        async with self.session.begin():
            user = await self.session.scalar(select(User).where(User.email == email))
            return user

    async def get_by_id(self, user_id: int) -> User | None:
        async with self.session.begin():
            return await self.session.scalar(select(User).where(User.id == user_id))

    async def email_is_exist(self, email: str) -> bool:
        async with self.session.begin():
            return await self.session.scalar(select(exists().where(User.email == email)))

    async def create(self, user_schema: UserCreateSchema) -> User:
        async with self.session.begin():
            user = User(**user_schema.model_dump())
            self.session.add(user)
            return user

    async def reset(self, user_schema: UserResetSchema) -> User | None:
        async with self.session.begin():
            hashed = password_hash.hash(user_schema.password)
            stmt = update(User).where(User.email == user_schema.email).values(_password=hashed)
            await self.session.execute(stmt)
        return await self.get_by_email(email=user_schema.email)

    async def update_profile(self, user_id: int, username: str = None, avatar: str = None) -> User | None:
        async with self.session.begin():
            values = {}
            if username is not None:
                values["username"] = username
            if avatar is not None:
                values["avatar"] = avatar
            if values:
                await self.session.execute(
                    update(User).where(User.id == user_id).values(**values)
                )
        return await self.get_by_id(user_id)

    async def change_password(self, user_id: int, new_password: str) -> None:
        async with self.session.begin():
            hashed = password_hash.hash(new_password)
            await self.session.execute(
                update(User).where(User.id == user_id).values(_password=hashed)
            )

class EmailCodeRepository:
    def __init__(self,session: AsyncSession):
        self.session = session

    async def create(self,email: str,code: str) -> EmailCode:
        async with self.session.begin():
            email_code = EmailCode(email=email,code=code)
            self.session.add(email_code)
            return email_code

    async def check_email_code(self,email: str,code: str) -> bool:
        async with self.session.begin():
            stmt = select(EmailCode).where(EmailCode.email == email,EmailCode.code == code)
            email_code: EmailCode | None = await self.session.scalar(stmt)
            if email_code is None:
                return False
            if (datetime.now() - email_code.create_time) > timedelta(minutes=10):
                return False
            return True