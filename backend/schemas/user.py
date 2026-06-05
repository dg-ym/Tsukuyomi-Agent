from pydantic import BaseModel,EmailStr,Field,model_validator
from typing import Annotated, Optional

UsernameStr = Annotated[str,Field(min_length=1,max_length=20,description="用户名")]
PasswordStr = Annotated[str,Field(min_length=6,max_length=20,description="密码")]

class RegisterIn(BaseModel):
    email: EmailStr
    username: UsernameStr
    password: PasswordStr
    confirm_password: PasswordStr
    code: Annotated[str,Field(min_length=4,max_length=4,description="邮箱验证码")]

    # 进行后续校验
    @model_validator(mode="after")
    def password_is_math(self):
        if self.password != self.confirm_password:
            raise ValueError("密码不一致")
        return self


class UserCreateSchema(BaseModel):
    email: EmailStr
    username: UsernameStr
    password: PasswordStr

class LoginIn(BaseModel):
    email: EmailStr
    password: PasswordStr

class UserSchema(BaseModel):
    id: Annotated[int,Field(...)]
    email: EmailStr
    username: UsernameStr

class LoginOut(BaseModel):
    user: UserSchema
    token: str
    refresh_token: str

class RefreshIn(BaseModel):
    refresh_token: str

class RefreshOut(BaseModel):
    token: str
    refresh_token: str

class UserResetSchema(BaseModel):
    email: EmailStr
    code: Annotated[str,Field(min_length=4,max_length=4,description="邮箱验证码")]
    password: PasswordStr


class UserProfileOut(BaseModel):
    """用户信息响应"""
    id: int
    email: str
    username: str
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateProfileIn(BaseModel):
    """修改用户信息"""
    username: Optional[str] = None
    avatar: Optional[str] = None


class ChangePasswordIn(BaseModel):
    """修改密码"""
    old_password: str
    new_password: PasswordStr
    confirm_password: PasswordStr

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("密码不一致")
        return self