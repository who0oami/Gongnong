from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ScreenMode = Literal["easy", "standard"]


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
    onboarding_completed: bool
    screen_mode: ScreenMode | None
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CompleteOnboardingRequest(BaseModel):
    # Optional: omit to keep onboarding_completed-only behavior (existing callers), or send it from
    # OnboardingPage's finish() to persist the screen mode chosen in onboarding step 4.
    screen_mode: ScreenMode | None = None
