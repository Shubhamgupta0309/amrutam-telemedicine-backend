from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import func, select, and_, not_, or_
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException, ValidationException
from app.modules.audit.service import record_audit_log
from app.modules.doctors.models import AvailabilitySlot, Doctor
from app.modules.doctors.schemas import SlotCreate
from app.modules.users.models import Profile, User


def search_doctors(
    db: Session,
    specialty: Optional[str] = None,
    verified_only: bool = True,
    page: int = 1,
    size: int = 20,
) -> Tuple[List[dict], int]:
    query = (
        select(Doctor, Profile.name)
        .join(User, Doctor.user_id == User.id)
        .outerjoin(Profile, User.id == Profile.user_id)
    )

    if verified_only:
        query = query.where(Doctor.verification_status == "VERIFIED")

    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty.strip()}%"))

    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_stmt) or 0

    # Paginate
    offset = (page - 1) * size
    results = db.execute(query.offset(offset).limit(size)).all()

    doctor_list = []
    for doc, name in results:
        doctor_list.append({
            "id": doc.id,
            "user_id": doc.user_id,
            "name": name or "Doctor",
            "specialty": doc.specialty,
            "registration_number": doc.registration_number,
            "verification_status": doc.verification_status,
            "consultation_fee": doc.consultation_fee,
            "bio": doc.bio,
        })

    return doctor_list, total


def get_doctor_by_id(db: Session, doctor_id: str) -> dict:
    stmt = (
        select(Doctor, Profile.name)
        .join(User, Doctor.user_id == User.id)
        .outerjoin(Profile, User.id == Profile.user_id)
        .where(Doctor.id == doctor_id)
    )
    res = db.execute(stmt).first()
    if not res:
        raise NotFoundException("Doctor", doctor_id)

    doc, name = res
    return {
        "id": doc.id,
        "user_id": doc.user_id,
        "name": name or "Doctor",
        "specialty": doc.specialty,
        "registration_number": doc.registration_number,
        "verification_status": doc.verification_status,
        "consultation_fee": doc.consultation_fee,
        "bio": doc.bio,
    }


def get_available_slots(
    db: Session,
    doctor_id: str,
    from_time: Optional[datetime] = None
) -> List[AvailabilitySlot]:
    # Verify doctor exists
    doctor = db.scalar(select(Doctor).where(Doctor.id == doctor_id))
    if not doctor:
        raise NotFoundException("Doctor", doctor_id)

    now = from_time or datetime.now(timezone.utc)
    stmt = (
        select(AvailabilitySlot)
        .where(
            AvailabilitySlot.doctor_id == doctor_id,
            AvailabilitySlot.status == "AVAILABLE",
            AvailabilitySlot.start_at >= now,
        )
        .order_by(AvailabilitySlot.start_at.asc())
    )
    return list(db.scalars(stmt).all())


def create_slot(
    db: Session,
    doctor_id: str,
    slot_data: SlotCreate,
    current_user_id: str
) -> AvailabilitySlot:
    doctor = db.scalar(select(Doctor).where(Doctor.id == doctor_id))
    if not doctor:
        raise NotFoundException("Doctor", doctor_id)

    if doctor.user_id != current_user_id:
        raise ForbiddenException("You cannot manage availability for another doctor")

    if doctor.verification_status != "VERIFIED":
        raise ForbiddenException("Unverified doctors cannot publish availability slots")

    # Check for slot overlap for this doctor
    overlap_stmt = select(func.count(AvailabilitySlot.id)).where(
        AvailabilitySlot.doctor_id == doctor_id,
        AvailabilitySlot.status.in_(["AVAILABLE", "RESERVED", "BOOKED"]),
        not_(
            or_(
                AvailabilitySlot.end_at <= slot_data.start_at,
                AvailabilitySlot.start_at >= slot_data.end_at
            )
        )
    )
    overlap_count = db.scalar(overlap_stmt) or 0
    if overlap_count > 0:
        raise ConflictException(
            detail="Doctor already has an active or booked slot overlapping with this time range",
            error_code="SLOT_OVERLAP_CONFLICT"
        )

    new_slot = AvailabilitySlot(
        doctor_id=doctor_id,
        start_at=slot_data.start_at,
        end_at=slot_data.end_at,
        status="AVAILABLE"
    )
    db.add(new_slot)

    record_audit_log(
        db=db,
        action="SLOT_CREATED",
        resource_type="availability_slot",
        actor_id=current_user_id,
        resource_id=new_slot.id,
        details={
            "doctor_id": doctor_id,
            "start_at": slot_data.start_at.isoformat(),
            "end_at": slot_data.end_at.isoformat()
        }
    )

    db.commit()
    db.refresh(new_slot)
    return new_slot


def verify_doctor_status(
    db: Session,
    doctor_id: str,
    admin_id: str,
    status: str = "VERIFIED"
) -> Doctor:
    doctor = db.scalar(select(Doctor).where(Doctor.id == doctor_id))
    if not doctor:
        raise NotFoundException("Doctor", doctor_id)

    doctor.verification_status = status
    record_audit_log(
        db=db,
        action="DOCTOR_VERIFICATION_STATUS_CHANGED",
        resource_type="doctor",
        actor_id=admin_id,
        resource_id=doctor.id,
        details={"new_status": status}
    )
    db.commit()
    db.refresh(doctor)
    return doctor
