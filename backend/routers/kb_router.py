import os
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from models import AsyncSessionFactory
from models.user_file import UserDocument
from core.auth import AuthHandler
from rag.vector_store import vector_store
from sqlalchemy import select
from utils.context_vars import current_user_id

auth_handler = AuthHandler()

router = APIRouter(prefix="/kb", tags=["knowledge_base"])

security_scheme = HTTPBearer()


def get_current_user_id(
    auth: HTTPAuthorizationCredentials = Security(security_scheme)
) -> str:
    return auth_handler.decode_access_token(auth.credentials)


ALLOWED_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv"}


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    md5_hash: str
    content_preview: str
    create_time: str

    class Config:
        from_attributes = True


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    user_id: str = Depends(get_current_user_id)
):
    """获取当前用户的所有知识库文档"""
    db = AsyncSessionFactory()
    try:
        result = await db.scalars(
            select(UserDocument)
            .where(UserDocument.user_id == int(user_id))
            .order_by(UserDocument.create_time.desc())
        )
        docs = list(result.all())
        return [
            DocumentOut(
                id=d.id,
                filename=d.filename,
                file_type=d.file_type,
                file_size=d.file_size,
                md5_hash=d.md5_hash,
                content_preview=d.content_preview,
                create_time=d.create_time.isoformat()
            ) for d in docs
        ]
    finally:
        await db.close()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id)
):
    """上传文档到当前用户的知识库（仅存 MySQL + ChromaDB，不写磁盘）"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail=f"不支持的文件类型: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()

    # 计算MD5（内存中）
    import hashlib
    md5_hash = hashlib.md5(content).hexdigest()

    # 数据库去重检查
    db = AsyncSessionFactory()
    try:
        existing = await db.scalar(
            select(UserDocument)
            .where(UserDocument.user_id == int(user_id), UserDocument.md5_hash == md5_hash)
        )
        if existing:
            raise HTTPException(409, detail="该文件已存在（MD5重复）")

        # 存入向量库
        chunk_count = vector_store.load_from_content(int(user_id), content, file.filename, md5_hash)

        # 内容预览
        try:
            text_content = content.decode("utf-8")[:500]
        except UnicodeDecodeError:
            text_content = "<二进制文件>"

        # 存入数据库
        doc = UserDocument(
            user_id=int(user_id),
            filename=file.filename,
            file_type=ext[1:],
            file_size=len(content),
            md5_hash=md5_hash,
            content_preview=text_content,
        )
        db.add(doc)
        await db.commit()

        return {
            "code": 100,
            "data": {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "chunk_count": chunk_count,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, detail=f"上传失败: {str(e)}")
    finally:
        await db.close()


class RenameDocRequest(BaseModel):
    filename: str


@router.put("/documents/{doc_id}/rename")
async def rename_document(
    doc_id: int,
    data: RenameDocRequest,
    user_id: str = Depends(get_current_user_id)
):
    """重命名文档"""
    db = AsyncSessionFactory()
    try:
        doc = await db.scalar(
            select(UserDocument)
            .where(UserDocument.id == doc_id, UserDocument.user_id == int(user_id))
        )
        if not doc:
            raise HTTPException(404, detail="文档不存在")

        new_name = data.filename.strip()
        if not new_name:
            raise HTTPException(400, detail="文件名不能为空")

        # 保留扩展名
        old_ext = os.path.splitext(doc.filename)[1]
        if not new_name.endswith(old_ext):
            new_name = new_name.split(".")[0] + old_ext

        doc.filename = new_name
        await db.commit()
        return {"result": "success"}
    finally:
        await db.close()


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    user_id: str = Depends(get_current_user_id)
):
    """删除指定文档（从数据库和向量库中移除）"""
    db = AsyncSessionFactory()
    try:
        doc = await db.scalar(
            select(UserDocument)
            .where(UserDocument.id == doc_id, UserDocument.user_id == int(user_id))
        )
        if not doc:
            raise HTTPException(404, detail="文档不存在")

        # 从向量库删除
        vector_store.delete_document(int(user_id), doc.md5_hash)

        # 从数据库删除
        await db.delete(doc)
        await db.commit()

        return {"result": "success"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, detail=f"删除失败: {str(e)}")
    finally:
        await db.close()
