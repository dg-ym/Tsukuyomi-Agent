import datetime
import json
from typing import List
from . import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey, JSON, DateTime, Text
from sqlalchemy.sql import func
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    email: Mapped[str] = mapped_column(String(100),unique=True,index=True)
    username: Mapped[str] = mapped_column(String(100))
    _password: Mapped[str] = mapped_column(String(200))     # 加密后的密码
    avatar: Mapped[str | None] = mapped_column(Text(4294967295), nullable=True, comment="头像base64(LONGTEXT)")

    # 对传进来的password进行加密，*args 位置传参，**kwargs 关键字传参
    def __init__(self,*args,**kwargs):
        password = kwargs.pop("password")
        super().__init__(*args,**kwargs)
        if password:
            self.password = password

    # get方法
    @property
    def password(self):
        return self._password

    # set方法
    @password.setter
    def password(self,raw_password):
        self._password = password_hash.hash(raw_password)

    def check_password(self,raw_password):
        return password_hash.verify(raw_password,self.password)

    chat_sessions: Mapped[List["ChatSession"]] = relationship("ChatSession",back_populates="user",cascade="all, delete-orphan")
# 邮箱验证码，后续用Redis实现
class EmailCode(Base):
    __tablename__ = "email_code"
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    email: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(10))
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    title: Mapped[str] = mapped_column(String(100),default="新的对话")
    metadata_: Mapped[json] = mapped_column(JSON,name="metadata")
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey("user.id"))
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())

    user: Mapped[User] = relationship("User",back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage",back_populates="session",cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer,ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(32),nullable=False)
    content: Mapped[str] = mapped_column(Text,nullable=False)
    metadata_: Mapped[json] = mapped_column(JSON,name="metadata")
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

    session: Mapped[ChatSession] = relationship("ChatSession",back_populates="messages")