from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.doctors import service
from app.modules.doctors.schemas import DoctorListResponse, DoctorRead, SlotCreate, SlotRead
from app.modules.users.models import User

router = APIRouter(prefix="/doctors", tags=["Doctors & Availability"])


@router.get("", response_model=DoctorListResponse)
def list_doctors(
    specialty: Optional[str] = Query(None, description="Filter by doctor specialty"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Search and filter verified doctors by specialty with pagination."""
    items, total = service.search_doctors(
        db=db,
        specialty=specialty,
        verified_only=True,
        page=page,
        size=size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/{id}", response_model=DoctorRead)
def get_doctor(
    id: str,
    db: Session = Depends(get_db)
):
    """Get detailed profile for a specific doctor."""
    return service.get_doctor_by_id(db=db, doctor_id=id)


@router.get("/{id}/availability", response_model=List[SlotRead])
def get_doctor_availability(
    id: str,
    db: Session = Depends(get_db)
):
    """Retrieve all upcoming AVAILABLE time slots for a doctor."""
    return service.get_available_slots(db=db, doctor_id=id)


@router.post("/{id}/availability", response_model=SlotRead, status_code=status.HTTP_201_CREATED)
def create_doctor_slot(
    id: str,
    slot_data: SlotCreate,
    current_user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db)
):
    """Create a new availability slot. Only the authenticated doctor owning the profile can create slots."""
    return service.create_slot(
        db=db,
        doctor_id=id,
        slot_data=slot_data,
        current_user_id=current_user.id
    )


@router.post("/{id}/verify", status_code=status.HTTP_200_OK)
def verify_doctor(
    id: str,
    verification_status: str = Query("VERIFIED", pattern="^(VERIFIED|REJECTED|PENDING)$"),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Admin endpoint to verify or reject a doctor's medical credentials."""
    doc = service.verify_doctor_status(
        db=db,
        doctor_id=id,
        admin_id=current_user.id,
        status=verification_status
    )
    return {
        "message": f"Doctor verification status updated to {verification_status}",
        "doctor_id": doc.id,
        "verification_status": doc.verification_status
    }
