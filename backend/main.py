from fastapi import FastAPI, Depends
from fastapi_mail import MessageSchema, FastMail, MessageType
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies import get_session, get_mail
from models.user import User
from schemas.user import UserCreateSchema
from routers.user_router import router as user_router
from routers.agent_router import router as agent_router
from routers.kb_router import router as kb_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有；生产写具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(user_router)
app.include_router(agent_router)
app.include_router(kb_router)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("hello/{name}")
async def hello(name: str):
    return {"message": f"Hello {name}"}

@app.get("/mail/test")
async def mail_test(
        email: str,
        mail: FastMail = Depends(get_mail)
):
    message = MessageSchema(
        subject="hello",
        recipients=[email],
        body=f"hello{email}",
        subtype=MessageType.plain
    )
    await mail.send_message(message)
    return {"message": "邮件发送成功！"}

@app.post('/user/add',response_model=UserCreateSchema)
async def add_user(session: AsyncSession=Depends(get_session)):
    async with session.begin():
        user = User(email="123456@qq.com",username="test_name",password="123456")
        session.add(user)
    return user