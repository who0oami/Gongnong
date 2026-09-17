from datetime import datetime

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=1)
    username: str = Field(min_length=4, max_length=50)
    email: str
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
