from models import AsyncSessionFactory
from core.mail import create_mail_instance
from fastapi_mail import FastMail

async def get_mail() -> FastMail:
    return create_mail_instance()

async def get_session():
    session = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()