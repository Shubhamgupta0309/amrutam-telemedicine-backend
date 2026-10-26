from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.modules.doctors.schemas import SlotRead


class BookingCreate(BaseModel):
    doctor_id: str = Field(..., description="Target doctor UUID")
    slot_id: str = Field(..., description="Target availability slot UUID")
    notes: Optional[str] = Field(None, max_length=1000, description="Chief complaints or booking notes")


class BookingRead(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    slot_id: str
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    slot: Optional[SlotRead] = None

    model_config = {"from_attributes": True}


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)
