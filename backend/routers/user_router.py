from fastapi import APIRouter,Query,Depends,HTTPException
from pydantic import EmailStr
from typing import Annotated
from dependencies import get_mail,get_session
from fastapi_mail import FastMail,MessageSchema,MessageType
from models import AsyncSession
import string
import random
from aiosmtplib import SMTPResponseException

from models.user import User
from respository.user_repo import UserRepository
from schemas import ResponseOut
from utils.cache_service import cache_user_info, set_email_code, verify_email_code
from schemas.user import RegisterIn, UserCreateSchema, LoginIn, LoginOut, UserResetSchema, UserProfileOut, UpdateProfileIn, ChangePasswordIn
from core.auth import AuthHandler
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Security

router = APIRouter(prefix="/user", tags=["user"])

auth_handler = AuthHandler()
security_scheme = HTTPBearer()


def get_auth_user_id(auth: HTTPAuthorizationCredentials = Security(security_scheme)) -> str:
    return auth_handler.decode_access_token(auth.credentials)

@router.get("/code",response_model=ResponseOut)
async def get_email_code(
        email: Annotated[EmailStr,Query(...)],
        mail: FastMail = Depends(get_mail)
):
    # 生成四位数字验证码
    source = string.digits
    code = "".join(random.sample(source,4))
    # 创建消息对象
    message = MessageSchema(
        subject="【月读】注册验证码",
        recipients=[email],
        body=f"您的验证码是：{code}，十分钟内有效！",
        subtype=MessageType.plain
    )
    mail_success = False
    try:
        await mail.send_message(message)
        mail_success = True
    except SMTPResponseException as e:
        if e.code == -1 and b"\\x00\\x00\\x00" in str(e).encode():
            print("忽略 QQ邮箱 SMTP关闭阶段的非标准响应(邮件已成功发送)")
            mail_success = True
        else:
            raise HTTPException(500, detail="邮件发送失败！")
    if mail_success:
        await set_email_code(str(email), code)
    return ResponseOut()

@router.post("/register",response_model=ResponseOut)
async def register(
        data: RegisterIn,
        session: AsyncSession = Depends(get_session)
):
    user_repo = UserRepository(session=session)
    # 判断邮箱是否已存在
    email_exist = await user_repo.email_is_exist(email=str(data.email))
    if email_exist:
        raise HTTPException(400,detail="该邮箱已存在！")
    # 从 Redis 校验验证码
    if not await verify_email_code(str(data.email), str(data.code)):
        raise HTTPException(400,detail="验证码错误或已过期！")
    try:
        await user_repo.create(UserCreateSchema(email=str(data.email),password=data.password,username=data.username))
    except Exception as e:
        raise HTTPException(500,detail=str(e))
    return ResponseOut()

@router.post("/login",response_model=LoginOut)
async def login(
        data: LoginIn,
        session: AsyncSession = Depends(get_session)
):
    # 创建user_repo对象
    user_repo = UserRepository(session=session)
    # 根据邮箱查找用户
    user: User|None = await user_repo.get_by_email(email=str(data.email))
    if not user:
        raise HTTPException(400,detail="该用户不存在！")
    if not user.check_password(data.password):
        raise HTTPException(400,detail="邮箱或密码错误！")
    tokens = auth_handler.encode_login_token(user.id)
    # 缓存用户信息到 Redis
    await cache_user_info(user.id, {"id": str(user.id), "email": user.email, "username": user.username})
    return {
        "user": user,
        "token": tokens["access_token"]
    }

@router.put("/reset",response_model=ResponseOut)
async def reset_password(
        data: UserResetSchema,
        session: AsyncSession = Depends(get_session)
):
    user_repo = UserRepository(session=session)
    email_exist = await user_repo.email_is_exist(email=str(data.email))
    if not email_exist:
        raise HTTPException(400,detail="该邮箱不存在！")
    if not await verify_email_code(str(data.email), str(data.code)):
        raise HTTPException(400,detail="验证码错误或已过期！")
    try:
        await user_repo.reset(UserResetSchema(email=str(data.email),code=str(data.code),password=data.password))
    except Exception as e:
        raise HTTPException(500,detail=str(e))
    return ResponseOut()


# 个人中心

@router.get("/profile", response_model=UserProfileOut)
async def get_profile(
    user_id: str = Depends(get_auth_user_id),
    session: AsyncSession = Depends(get_session)
):
    """获取当前用户信息"""
    repo = UserRepository(session=session)
    user = await repo.get_by_id(int(user_id))
    if not user:
        raise HTTPException(404, detail="用户不存在")
    return user


@router.put("/profile", response_model=UserProfileOut)
async def update_profile(
    data: UpdateProfileIn,
    user_id: str = Depends(get_auth_user_id),
    session: AsyncSession = Depends(get_session)
):
    """修改用户名/头像"""
    repo = UserRepository(session=session)
    user = await repo.update_profile(
        int(user_id),
        username=data.username,
        avatar=data.avatar
    )
    if not user:
        raise HTTPException(404, detail="用户不存在")
    return user


@router.put("/password")
async def change_password(
    data: ChangePasswordIn,
    user_id: str = Depends(get_auth_user_id),
    session: AsyncSession = Depends(get_session)
):
    """修改密码"""
    repo = UserRepository(session=session)
    user = await repo.get_by_id(int(user_id))
    if not user:
        raise HTTPException(404, detail="用户不存在")
    if not user.check_password(data.old_password):
        raise HTTPException(400, detail="原密码错误")
    await repo.change_password(int(user_id), data.new_password)
    return {"result": "success"}


# 注销账号

@router.delete("/account")
async def delete_account(
    user_id: str = Depends(get_auth_user_id),
    session: AsyncSession = Depends(get_session)
):
    """注销账号，删除用户所有数据"""
    uid = int(user_id)

    # 1. 删除 MySQL 数据 (User 级联删除 sessions/messages/documents)
    from models.user import User, ChatSession, ChatMessage
    from models.user_file import UserDocument
    from sqlalchemy import delete, select
    from utils.cache_service import get_redis

    user_repo = UserRepository(session=session)
    user = await user_repo.get_by_id(uid)
    if not user:
        raise HTTPException(404, detail="用户不存在")

    async with session.begin():
        # 按子→父顺序删除，避免外键约束冲突
        await session.execute(
            delete(ChatMessage).where(
                ChatMessage.session_id.in_(
                    select(ChatSession.id).where(ChatSession.user_id == uid)
                )
            )
        )
        await session.execute(delete(ChatSession).where(ChatSession.user_id == uid))
        await session.execute(delete(UserDocument).where(UserDocument.user_id == uid))
        await session.execute(delete(User).where(User.id == uid))

    # 2. 删除 ChromaDB 数据
    try:
        from langchain_chroma import Chroma
        from models.factory import embed_model
        kb_collection = f"kb_user_{uid}"
        Chroma(collection_name=kb_collection, embedding_function=embed_model,
               persist_directory="chroma_db").delete_collection()
    except Exception as e:
        print(f"[注销] ChromaDB kb 清理失败: {e}")

    # 3. 删除 Redis 缓存
    try:
        r = await get_redis()
        keys = await r.keys(f"*:{uid}") + await r.keys(f"*:{uid}:*")
        for key in set(keys):
            await r.delete(key)
    except Exception as e:
        print(f"[注销] Redis 清理失败: {e}")

    return {"result": "success"}