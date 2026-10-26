from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class MedicationItem(BaseModel):
    name: str = Field(..., min_length=1, description="Medication or formulation name")
    dosage: str = Field(..., description="e.g. 500mg, 1 tablet, 10ml")
    frequency: str = Field(..., description="e.g. Twice daily after meals")
    duration: str = Field(..., description="e.g. 7 days, 1 month")
    instructions: Optional[str] = None


class ConsultationStart(BaseModel):
    notes: Optional[str] = None


class ConsultationComplete(BaseModel):
    final_notes: Optional[str] = None


class PrescriptionCreate(BaseModel):
    diagnosis: str = Field(..., min_length=2, description="Clinical diagnosis or assessment")
    medications: List[MedicationItem] = Field(..., min_length=1, description="List of prescribed medicines")
    instructions: Optional[str] = Field(None, description="General lifestyle, dietary, or follow-up instructions")


class PrescriptionRead(BaseModel):
    id: str
    consultation_id: str
    doctor_id: str
    patient_id: str
    diagnosis: str
    medications: List[MedicationItem]
    instructions: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
