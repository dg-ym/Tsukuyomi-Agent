"""
Redis 滑动窗口 + ChromaDB 长期记忆 缓存服务
"""
import json
import redis.asyncio as aioredis
from datetime import timedelta

from models.factory import embed_model
from utils.logger_handler import logger

# ==================== Redis 配置 ====================
REDIS_URL = "redis://127.0.0.1:6379/0"
SESSION_TTL = int(timedelta(days=30).total_seconds())  # 30天
WINDOW_SIZE = 20  # 滑动窗口保留最近20条

_redis = None


async def _get_redis():
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                REDIS_URL, decode_responses=True,
                socket_connect_timeout=2, socket_timeout=2,
                retry_on_timeout=False,
                protocol=2  # Redis 5.x 仅支持 RESP2
            )
            # 测试连接
            await _redis.ping()
            logger.info("[Redis] 连接成功")
        except Exception as e:
            logger.warning(f"[Redis] 连接失败，缓存功能禁用: {e}")
            _redis = False
    if _redis is False:
        return None
    return _redis


def _session_key(session_id: int) -> str:
    return f"chat:{session_id}"


def _user_key(user_id: int) -> str:
    return f"user:{user_id}"


# ==================== 会话消息缓存 ====================

async def cache_chat_messages(session_id: int, messages: list[dict]):
    """将消息列表推入 Redis 滑动窗口"""
    r = await _get_redis()
    if not r:
        return
    key = _session_key(session_id)
    for msg in reversed(messages):  # LPUSH 保持时间顺序
        await r.lpush(key, json.dumps(msg, ensure_ascii=False))
    await r.ltrim(key, 0, WINDOW_SIZE - 1)
    await r.expire(key, SESSION_TTL)


async def get_cached_messages(session_id: int) -> list[dict]:
    """从 Redis 获取会话最近消息"""
    r = await _get_redis()
    if not r:
        return []
    key = _session_key(session_id)
    raw = await r.lrange(key, 0, -1)
    if not raw:
        return []
    messages = [json.loads(m) for m in reversed(raw)]
    # 刷新 TTL
    await r.expire(key, SESSION_TTL)
    return messages


async def push_single_message(session_id: int, msg: dict):
    """追加单条消息到窗口"""
    r = await _get_redis()
    if not r:
        return
    key = _session_key(session_id)
    await r.lpush(key, json.dumps(msg, ensure_ascii=False))
    await r.ltrim(key, 0, WINDOW_SIZE - 1)
    await r.expire(key, SESSION_TTL)


# 邮箱验证码缓存

EMAIL_CODE_TTL = 600  # 10分钟


async def set_email_code(email: str, code: str):
    r = await _get_redis()
    if not r:
        return
    await r.setex(f"email_code:{email}", EMAIL_CODE_TTL, code)


async def verify_email_code(email: str, code: str) -> bool:
    r = await _get_redis()
    if not r:
        return False
    stored = await r.get(f"email_code:{email}")
    if stored and stored == code:
        await r.delete(f"email_code:{email}")  # 一次性验证码
        return True
    return False


# 用户缓存

async def cache_user_info(user_id: int, data: dict):
    r = await _get_redis()
    if not r:
        return
    await r.hset(_user_key(user_id), mapping={k: str(v) for k, v in data.items()})
    await r.expire(_user_key(user_id), SESSION_TTL)


async def get_cached_user(user_id: int) -> dict | None:
    r = await _get_redis()
    if not r:
        return None
    data = await r.hgetall(_user_key(user_id))
    return data if data else None


# 公开 get_redis 供外部清理缓存使用
get_redis = _get_redis


# ChromaDB长期记忆

CHAT_CHROMA_DIR = "chroma_db"
CHAT_COLLECTION = "chat_history"


async def store_chat_to_chroma(session_id: int, role: str, content: str):
    """将单条聊天记录存入 ChromaDB 长期记忆"""
    if not content or len(content) < 5:
        return
    try:
        from langchain_chroma import Chroma
        chroma = Chroma(
            collection_name=CHAT_COLLECTION,
            embedding_function=embed_model,
            persist_directory=CHAT_CHROMA_DIR,
        )
        chroma.add_texts(
            texts=[content],
            metadatas=[{"session_id": session_id, "role": role}],
        )
    except Exception as e:
        logger.warning(f"[ChromaDB] 存储聊天失败: {e}")
