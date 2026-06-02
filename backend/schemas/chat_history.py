from pydantic import BaseModel
from datetime import datetime


class SessionOut(BaseModel):
    """会话列表响应"""
    id: int
    title: str
    user_id: int
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    """消息列表响应"""
    id: int
    session_id: int
    role: str
    content: str
    create_time: datetime

    class Config:
        from_attributes = True


class RenameRequest(BaseModel):
    """重命名请求"""
    title: str
