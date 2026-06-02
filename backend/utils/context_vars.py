"""
全局上下文变量，用于在异步调用链中传递用户ID等信息
"""
from contextvars import ContextVar

# 当前请求的用户ID
current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
