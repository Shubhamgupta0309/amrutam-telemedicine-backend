from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    name: str = Field(..., min_length=2, max_length=255)
    role: str = Field("patient", pattern="^(patient|doctor)$")
    phone: Optional[str] = None
    timezone: str = "UTC"
    # Doctor specific fields
    specialty: Optional[str] = None
    registration_number: Optional[str] = None
    consultation_fee: Optional[float] = 500.0


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    mfa_required: bool = False


class MFAChallengeResponse(BaseModel):
    mfa_required: bool = True
    temp_token: str
    message: str = "MFA code required to complete authentication"


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
    temp_token: Optional[str] = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str
