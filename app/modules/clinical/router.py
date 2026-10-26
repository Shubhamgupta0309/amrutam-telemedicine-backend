from typing import List
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.clinical import service
from app.modules.clinical.schemas import (
    ConsultationComplete,
    ConsultationStart,
    PrescriptionCreate,
    PrescriptionRead,
)
from app.modules.bookings.schemas import BookingRead
from app.modules.users.models import User

router = APIRouter(prefix="/consultations", tags=["Clinical Workflows & Prescriptions"])


@router.post("/{id}/start", response_model=BookingRead)
def start_consultation(
    id: str,
    data: ConsultationStart,
    request: Request,
    current_user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
):
    """Transition consultation status from SCHEDULED to IN_PROGRESS. Doctor only."""
    client_ip = request.client.host if request.client else None
    return service.start_consultation(
        db=db,
        consultation_id=id,
        doctor_user=current_user,
        notes=data.notes,
        ip_address=client_ip,
    )


@router.post("/{id}/complete", response_model=BookingRead)
def complete_consultation(
    id: str,
    data: ConsultationComplete,
    request: Request,
    current_user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
):
    """Transition consultation status from IN_PROGRESS to COMPLETED. Doctor only."""
    client_ip = request.client.host if request.client else None
    return service.complete_consultation(
        db=db,
        consultation_id=id,
        doctor_user=current_user,
        final_notes=data.final_notes,
        ip_address=client_ip,
    )


@router.post("/{id}/prescriptions", status_code=status.HTTP_201_CREATED)
def issue_prescription(
    id: str,
    prescription_data: PrescriptionCreate,
    request: Request,
    current_user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
):
    """Issue digital prescription for an in-progress or completed consultation. Doctor only."""
    client_ip = request.client.host if request.client else None
    prescription = service.issue_prescription(
        db=db,
        consultation_id=id,
        doctor_user=current_user,
        prescription_data=prescription_data,
        ip_address=client_ip,
    )
    return {
        "message": "Prescription issued successfully",
        "prescription_id": prescription.id,
        "consultation_id": prescription.consultation_id,
        "diagnosis": prescription.diagnosis,
    }


@router.get("/{id}/prescriptions", response_model=List[PrescriptionRead])
def get_prescriptions(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve prescriptions for a consultation. Accessible only to the patient or doctor involved."""
    return service.get_consultation_prescriptions(
        db=db,
        consultation_id=id,
        user=current_user,
    )
