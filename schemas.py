from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=20,pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: str = Field(min_length=3, max_length=100)
    # # [STORED XSS]
    # full_name: str = Field(min_length=3)
    email: EmailStr = Field(max_length=100)


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    image_file: str | None
    image_path: str
    date_joined: datetime


class UserPrivate(UserPublic):
    email: EmailStr


class UserUpdate(BaseModel):
    username: str = Field(default=None, min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: str | None = Field(default=None, min_length=3, max_length=100)
    # # [STORED XSS]
    # full_name: str | None = Field(default=None, min_length=3)
    email: EmailStr | None = Field(default=None, max_length=100)


class Token(BaseModel):
    access_token: str
    token_type: str