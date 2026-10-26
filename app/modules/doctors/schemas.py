from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class SlotCreate(BaseModel):
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "SlotCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be strictly after start_at")
        return self


class SlotRead(BaseModel):
    id: str
    doctor_id: str
    start_at: datetime
    end_at: datetime
    status: str

    model_config = {"from_attributes": True}


class DoctorRead(BaseModel):
    id: str
    user_id: str
    name: str
    specialty: str
    registration_number: str
    verification_status: str
    consultation_fee: float
    bio: Optional[str] = None

    model_config = {"from_attributes": True}


class DoctorListResponse(BaseModel):
    items: List[DoctorRead]
    total: int
    page: int
    size: int
