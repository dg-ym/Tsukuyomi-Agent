import datetime
from . import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from typing import Optional


class UserDocument(Base):
    """用户上传的知识库文档"""
    __tablename__ = "user_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255), comment="原始文件名")
    file_type: Mapped[str] = mapped_column(String(10), comment="文件后缀 txt/pdf/csv/docx/xlsx")
    file_size: Mapped[int] = mapped_column(Integer, comment="文件大小（字节）")
    md5_hash: Mapped[str] = mapped_column(String(32), comment="文件MD5值，用于去重")
    content_preview: Mapped[str] = mapped_column(String(500), comment="内容前500字预览")
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
