import json
import asyncio
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, Security, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional

from models import AsyncSessionFactory
from core.auth import AuthHandler
from agent.react_agent import ReactAgent
from respository.chat_history_repo import SessionRepository, MessageRepository
from schemas.chat_history import SessionOut, MessageOut, RenameRequest
from utils.context_vars import current_user_id
from utils.cache_service import (
    get_cached_messages, cache_chat_messages, push_single_message,
    store_chat_to_chroma,
)

auth_handler = AuthHandler()

router = APIRouter(prefix="/agent", tags=["agent"])

# 全局单例 agent，避免每次请求重新初始化
agent = ReactAgent()

# FastAPI 推荐的鉴权依赖写法：用独立函数 + Security
security_scheme = HTTPBearer()


def get_current_user_id(
    auth: HTTPAuthorizationCredentials = Security(security_scheme)
) -> str:
    return auth_handler.decode_access_token(auth.credentials)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="用户输入的问题")
    session_id: Optional[int] = Field(None, description="会话ID，不传则自动创建新会话")


async def sse_generator(query: str, user_id: int, session_id: int | None):
    """SSE 流式输出 + 自动保存会话记录"""
    db = AsyncSessionFactory()
    session_repo = SessionRepository(db)
    message_repo = MessageRepository(db)

    try:
        # 设置当前用户上下文，供 RAG 工具使用
        current_user_id.set(user_id)

        # 自动创建会话（如果没传 session_id）
        if session_id is None:
            # 标题：10字内直接用，超出则截断并加省略号
            title = query[:10] + ("..." if len(query) > 10 else "")
            sess = await session_repo.create(user_id=user_id, title=title)
            session_id = sess.id
            # 把新创建的 session_id 通知前端
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"

        # 1. 保存用户消息到 MySQL + Redis + ChromaDB
        await message_repo.create(session_id=session_id, role="user", content=query)
        await push_single_message(session_id, {"role": "user", "content": query})
        await store_chat_to_chroma(session_id, "user", query)

        # 2. 加载上下文：Redis 优先 → MySQL 兜底
        context_messages = None
        if session_id is not None:
            cached = await get_cached_messages(session_id)
            if cached and len(cached) > 1:
                # Redis 命中，去掉最后一条（当前用户消息）
                context_messages = cached[:-1][-20:]
                print(f"[MEMORY] Redis 命中 {len(cached)} 条, 传入 {len(context_messages)} 条")
            else:
                # Redis 未命中，从 MySQL 加载并回填缓存
                previous = await message_repo.get_by_session_id(session_id)
                context_messages = [
                    {"role": m.role, "content": m.content}
                    for m in previous[:-1]
                ][-20:]
                if previous:
                    await cache_chat_messages(session_id, context_messages)
                print(f"[MEMORY] MySQL 加载 {len(previous)} 条, 传入 {len(context_messages)} 条")

        # 3. 流式输出
        full_response = ""
        for event in agent.execute_stream(query, context_messages=context_messages):
            if event["type"] in ("content", "text"):
                full_response += event["data"]
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)

        # 4. 保存 AI 回复到 MySQL + Redis + ChromaDB
        if full_response.strip():
            await message_repo.create(
                session_id=session_id, role="assistant", content=full_response.strip()
            )
            await push_single_message(session_id, {"role": "assistant", "content": full_response.strip()})
            await store_chat_to_chroma(session_id, "assistant", full_response.strip())

        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        await db.close()


@router.post("/chat")
async def agent_chat(
    req: ChatRequest,
    user_id: str = Depends(get_current_user_id)
):
    """流式对话（SSE）+ 自动保存会话记录"""
    return StreamingResponse(
        sse_generator(req.query, int(user_id), req.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )



@router.post("/chat/sync")
async def agent_chat_sync(
    req: ChatRequest,
    user_id: str = Depends(get_current_user_id)
):
    """非流式对话 - 一次性返回完整回复"""
    full_response = ""
    for event in agent.execute_stream(req.query):
        if event["type"] in ("content", "text"):
            full_response += event["data"]
    return {"code": 100, "data": full_response}



@router.websocket("/chat/ws")
async def agent_chat_ws(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket 流式对话"""
    try:
        user_id = auth_handler.decode_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Token 无效或已过期")
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            query = data.get("query", "")

            if not query.strip():
                await websocket.send_json({"error": "query 不能为空"})
                continue

            for event in agent.execute_stream(query):
                await websocket.send_json(event)

            await websocket.send_json({"done": True})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass


# 会话历史查询

@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user_id: str = Depends(get_current_user_id)
):
    """获取当前用户的所有会话列表"""
    db = AsyncSessionFactory()
    try:
        repo = SessionRepository(db)
        return await repo.get_by_user_id(user_id=int(user_id))
    finally:
        await db.close()


@router.get("/sessions/{session_id}", response_model=list[MessageOut])
async def get_session_messages(
    session_id: int,
    user_id: str = Depends(get_current_user_id)
):
    """获取指定会话的所有消息"""
    db = AsyncSessionFactory()
    try:
        # 验证该会话属于当前用户
        session_repo = SessionRepository(db)
        sess = await session_repo.get_by_id(session_id)
        if sess is None or sess.user_id != int(user_id):
            raise HTTPException(404, detail="会话不存在")

        message_repo = MessageRepository(db)
        return await message_repo.get_by_session_id(session_id)
    finally:
        await db.close()


@router.put("/sessions/{session_id}/rename")
async def rename_session(
    session_id: int,
    data: RenameRequest,
    user_id: str = Depends(get_current_user_id)
):
    """重命名会话"""
    db = AsyncSessionFactory()
    try:
        repo = SessionRepository(db)
        sess = await repo.get_by_id(session_id)
        if sess is None or sess.user_id != int(user_id):
            raise HTTPException(404, detail="会话不存在")

        title = data.title.strip()
        if not title:
            raise HTTPException(400, detail="标题不能为空")

        await repo.rename(session_id, title)
        return {"result": "success"}
    finally:
        await db.close()


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user_id: str = Depends(get_current_user_id)
):
    """删除指定会话（级联删除消息）"""
    db = AsyncSessionFactory()
    try:
        repo = SessionRepository(db)
        sess = await repo.get_by_id(session_id)
        if sess is None or sess.user_id != int(user_id):
            raise HTTPException(404, detail="会话不存在")

        await repo.delete(session_id)
        return {"result": "success"}
    finally:
        await db.close()
