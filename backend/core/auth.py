import jwt
import uuid
import json
import base64
from fastapi import HTTPException,Security
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from datetime import datetime
from enum import Enum
import settings
from starlette.status import HTTP_401_UNAUTHORIZED,HTTP_403_FORBIDDEN
from threading import Lock
from utils.cache_service import get_redis

class SingletonMeta(type):
    """这是一个线程安全的单例实现"""
    _instances = {}
    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args,**kwargs)
                cls._instances[cls] = instance

        return cls._instances[cls]

class TokenTypeEnum(Enum):
    ACCESS_TOKEN = 1
    REFRESH_TOKEN = 2

class AuthHandler(metaclass=SingletonMeta):
    security = HTTPBearer()

    secret = settings.JWT_SECRET_KEY

    # JWT的payload包含四个字段
    # iss: 签发者，存用户ID
    # sub: 主题，存token类型（"1" = ACCESS，"2" = REFRESH）
    # jti: JWT ID，唯一标识每个token，用于Rotation复用检测
    # exp: 过期时间
    def _encode_token(self,user_id: int,type: TokenTypeEnum):
        payload = dict(
            iss=str(user_id),
            sub=str(type.value),
            jti=str(uuid.uuid4())
        )
        to_encode = payload.copy()
        if type == TokenTypeEnum.ACCESS_TOKEN:
            exp = datetime.now() + settings.JWT_ACCESS_TOKEN_EXPIRES
        else:
            exp = datetime.now() + settings.JWT_REFRESH_TOKEN_EXPIRES
        to_encode.update({"exp": int(exp.timestamp())})
        return jwt.encode(to_encode,self.secret,algorithm='HS256')

    def encode_login_token(self,user_id: int):
        access_token = self._encode_token(user_id,TokenTypeEnum.ACCESS_TOKEN)
        refresh_token = self._encode_token(user_id,TokenTypeEnum.REFRESH_TOKEN)
        login_token = dict(
            access_token=f"{access_token}",
            refresh_token=f"{refresh_token}"
        )
        return login_token

    def encode_update_token(self,user_id):
        access_token = self._encode_token(user_id,TokenTypeEnum.ACCESS_TOKEN)
        update_token = dict(
            access_token=f"{access_token}"
        )
        return update_token

    # ==================== Refresh Token Rotation ====================

    @staticmethod
    def _extract_jti(token: str) -> str:
        """从 JWT 中提取 jti（不验证签名，Base64 解码）"""
        try:
            payload_b64 = token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("jti", "")
        except Exception:
            return ""

    async def store_refresh_token(self, user_id: int, refresh_token: str) -> None:
        """将 refresh token 的 jti 存入 Redis，用于 Rotation 校验"""
        jti = self._extract_jti(refresh_token)
        if not jti:
            return
        r = await get_redis()
        if not r:
            return
        ttl = int(settings.JWT_REFRESH_TOKEN_EXPIRES.total_seconds())
        await r.setex(f"refresh_token:{user_id}:{jti}", ttl, "valid")

    async def rotate_refresh_token(
        self, user_id: int, old_jti: str, new_refresh_token: str
    ) -> tuple:
        """
        轮换 refresh token：三态标记实现重用检测。

        Redis key 生命周期：
          "valid"  → 未被使用，允许刷新
          "used"   → 已被使用过，检测到重用攻击
          不存在    → Redis 数据丢失或 JWT 已过期（decode_refresh_token 已拦截），降级允许

        返回 (success: bool, reason: str)
            - success=True, reason="ok"               → 正常轮换
            - success=True, reason="redis_unavailable" → Redis 不可用，降级为无状态
            - success=False, reason="reuse_detected"   → 重用攻击，已撤销所有 token
        """
        new_jti = self._extract_jti(new_refresh_token)
        if not new_jti:
            return False, "invalid_token"

        r = await get_redis()
        if not r:
            return True, "redis_unavailable"

        old_key = f"refresh_token:{user_id}:{old_jti}"
        new_key = f"refresh_token:{user_id}:{new_jti}"
        status = await r.get(old_key)
        full_ttl = int(settings.JWT_REFRESH_TOKEN_EXPIRES.total_seconds())

        if status == "valid":
            # 正常轮换：旧 token 标记为 "used"（保留剩余 TTL），新 token 写入 "valid"
            remaining_ttl = await r.ttl(old_key)
            if remaining_ttl <= 0:
                remaining_ttl = full_ttl
            await r.setex(old_key, remaining_ttl, "used")
            await r.setex(new_key, full_ttl, "valid")
            return True, "ok"

        elif status == "used":
            # 重用检测：旧 token 已被使用过 → 撤销该用户所有 refresh token
            keys = await r.keys(f"refresh_token:{user_id}:*")
            if keys:
                await r.delete(*keys)
            return False, "reuse_detected"

        else:
            # key 不存在：可能 Redis 重启丢失数据，或 JWT 已自然过期
            # decode_refresh_token 已通过签名+过期校验，允许刷新并存储新 token
            await r.setex(new_key, full_ttl, "valid")
            return True, "ok"

    async def revoke_user_refresh_tokens(self, user_id: int) -> None:
        """撤销用户所有 refresh token（注销/改密时调用）

        注意：标记为 "used" 而非删除，这样后续任何旧 token 尝试刷新
        都会被 rotate_refresh_token 识别为重用攻击，而非误判为 Redis 丢失。
        """
        r = await get_redis()
        if not r:
            return
        keys = await r.keys(f"refresh_token:{user_id}:*")
        for key in keys:
            ttl = await r.ttl(key)
            if ttl > 0:
                await r.setex(key, ttl, "used")

    def decode_access_token(self,token):
        # ACCESS TOKEN: 不可用（过期/有问题），都用403错误
        try:
            # 解码JWT
            payload = jwt.decode(token,self.secret,algorithms=['HS256'])
            # 类型校验
            if payload['sub'] != str(TokenTypeEnum.ACCESS_TOKEN.value):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN,detail="Token类型错误！")
            # 返回用户ID
            return payload['iss']
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN,detail="Access Token已过期！")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN,detail="Access Token不可用！")

    def decode_refresh_token(self,token):
        # REFRESH TOKEN: 不可用（过期/有问题），都用401错误
        # 返回 (user_id, jti) 元组，jti 用于 Rotation 复用检测
        try:
            payload = jwt.decode(token,self.secret,algorithms=['HS256'])
            if payload['sub'] != str(TokenTypeEnum.REFRESH_TOKEN.value):
                raise HTTPException(status_code=HTTP_401_UNAUTHORIZED,detail="Token类型错误！")
            return payload['iss'], payload.get('jti', '')
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED,detail="Refresh Token已过期！")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED,detail="Refresh Token不可用！")

    def auth_access_dependency(self,auth: HTTPAuthorizationCredentials = Security(security)):
        return self.decode_access_token(auth.credentials)

    def auth_refresh_dependency(self,auth: HTTPAuthorizationCredentials = Security(security)):
        user_id, jti = self.decode_refresh_token(auth.credentials)
        return user_id, jti