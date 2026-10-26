from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class ProfileBase(BaseModel):
    name: str
    phone: Optional[str] = None
    timezone: str = "UTC"


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None


class ProfileRead(ProfileBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DoctorBrief(BaseModel):
    id: str
    specialty: str
    registration_number: str
    verification_status: str
    consultation_fee: float

    model_config = {"from_attributes": True}


class UserMeResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    status: str
    mfa_enabled: bool
    created_at: datetime
    profile: Optional[ProfileRead] = None
    doctor_profile: Optional[DoctorBrief] = None

    model_config = {"from_attributes": True}
