from models import AsyncSession
from sqlalchemy import select, update, delete
from models.user import ChatSession, ChatMessage
from datetime import datetime


class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, title: str = "新的对话") -> ChatSession:
        async with self.session.begin():
            sess = ChatSession(user_id=user_id, title=title, metadata_={})
            self.session.add(sess)
            return sess

    async def get_by_user_id(self, user_id: int) -> list[ChatSession]:
        async with self.session.begin():
            result = await self.session.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.update_time.desc())
            )
            return list(result.all())

    async def get_by_id(self, session_id: int) -> ChatSession | None:
        async with self.session.begin():
            return await self.session.scalar(
                select(ChatSession).where(ChatSession.id == session_id)
            )

    async def rename(self, session_id: int, title: str) -> None:
        async with self.session.begin():
            await self.session.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(title=title, update_time=datetime.now())
            )

    async def delete(self, session_id: int) -> None:
        async with self.session.begin():
            sess = await self.session.scalar(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            if sess:
                await self.session.delete(sess)


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, session_id: int, role: str, content: str) -> ChatMessage:
        async with self.session.begin():
            msg = ChatMessage(
                session_id=session_id, role=role, content=content, metadata_={}
            )
            self.session.add(msg)
            # 同步更新会话的 update_time
            await self.session.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(update_time=datetime.now())
            )
            return msg

    async def get_by_session_id(self, session_id: int) -> list[ChatMessage]:
        async with self.session.begin():
            result = await self.session.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.create_time.asc())
            )
            return list(result.all())
