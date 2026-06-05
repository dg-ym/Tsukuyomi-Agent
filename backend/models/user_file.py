import datetime
import os
from . import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from typing import Optional
import settings


class UserDocument(Base):
    """用户上传的知识库文档。

    原文件存储在磁盘（UPLOAD_DIR），MySQL 只存元数据和文件路径。
    ChromaDB 损坏时可从磁盘原文件重新构建向量库。
    """
    __tablename__ = "user_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255), comment="原始文件名")
    file_type: Mapped[str] = mapped_column(String(10), comment="文件后缀 txt/pdf/csv/docx/xlsx")
    file_size: Mapped[int] = mapped_column(Integer, comment="文件大小（字节）")
    md5_hash: Mapped[str] = mapped_column(String(32), comment="文件MD5值，用于去重")
    file_path: Mapped[str] = mapped_column(String(512), comment="磁盘存储路径")
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def content_preview(self) -> str:
        """从磁盘文件读取前 500 字符作为预览"""
        try:
            abs_path = os.path.join(settings.UPLOAD_DIR, self.file_path)
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(500)
        except Exception:
            return ""
