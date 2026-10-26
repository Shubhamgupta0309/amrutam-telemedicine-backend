import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import (
    AppException,
    ConflictException,
    ForbiddenException,
    IdempotencyConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.audit.service import record_audit_log
from app.modules.bookings.models import Consultation, IdempotencyRecord, OutboxEvent
from app.modules.bookings.schemas import BookingCreate
from app.modules.doctors.models import AvailabilitySlot, Doctor
from app.modules.users.models import User


def compute_request_hash(payload: Dict[str, Any], user_id: str) -> str:
    """Generate SHA256 checksum for idempotency payload comparison."""
    canonical_str = f"{user_id}:{json.dumps(payload, sort_keys=True)}"
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def book_appointment_atomic(
    db: Session,
    patient_id: str,
    booking_data: BookingCreate,
    idempotency_key: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Atomically reserve an availability slot and create a consultation.
    Enforces idempotency, strict row locking, and transactional outbox.
    """
    request_dict = booking_data.model_dump()
    req_hash = compute_request_hash(request_dict, patient_id)

    # 1. Idempotency Check
    if idempotency_key:
        idemp_stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.scope == "bookings:create",
            IdempotencyRecord.key == idempotency_key,
        )
        existing_idemp = db.scalar(idemp_stmt)
        if existing_idemp:
            if existing_idemp.request_hash == req_hash:
                # Same key and same payload: return previously computed response
                return json.loads(existing_idemp.response_body), existing_idemp.status_code
            else:
                # Same key with DIFFERENT payload: reject with conflict
                raise IdempotencyConflictException()

    try:
        # 2. Concurrency-safe atomic slot reservation using row-level locking
        # On PostgreSQL, with_for_update locks the selected row until transaction commit/rollback
        slot_stmt = (
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.id == booking_data.slot_id,
                AvailabilitySlot.doctor_id == booking_data.doctor_id,
            )
            .with_for_update()
        )
        slot = db.scalar(slot_stmt)

        if not slot:
            raise NotFoundException("AvailabilitySlot", booking_data.slot_id)

        if slot.status != "AVAILABLE":
            raise ConflictException(
                detail="This appointment slot is no longer available. It may have been reserved by another patient.",
                error_code="SLOT_ALREADY_RESERVED",
            )

        # Verify doctor verification status
        doctor = db.scalar(select(Doctor).where(Doctor.id == booking_data.doctor_id))
        if not doctor or doctor.verification_status != "VERIFIED":
            raise ValidationException("Appointments can only be booked with verified doctors")

        # 3. Transition slot status to BOOKED
        slot.status = "BOOKED"

        # 4. Create Consultation record
        consultation = Consultation(
            patient_id=patient_id,
            doctor_id=booking_data.doctor_id,
            slot_id=slot.id,
            status="SCHEDULED",
            idempotency_key=idempotency_key,
            notes=booking_data.notes,
        )
        db.add(consultation)
        db.flush()

        # 5. Create Transactional Outbox Event for async notification
        outbox_payload = {
            "consultation_id": consultation.id,
            "patient_id": patient_id,
            "doctor_id": booking_data.doctor_id,
            "slot_id": slot.id,
            "start_at": slot.start_at.isoformat(),
            "end_at": slot.end_at.isoformat(),
            "status": "SCHEDULED",
        }
        outbox_event = OutboxEvent(
            event_type="BOOKING_CONFIRMED",
            payload=json.dumps(outbox_payload),
            status="PENDING",
        )
        db.add(outbox_event)

        # 6. Audit Logging
        record_audit_log(
            db=db,
            action="BOOKING_CREATED",
            resource_type="consultation",
            actor_id=patient_id,
            resource_id=consultation.id,
            ip_address=ip_address,
            details={
                "slot_id": slot.id,
                "doctor_id": booking_data.doctor_id,
                "idempotency_key": idempotency_key,
            },
        )

        response_body = {
            "id": consultation.id,
            "patient_id": consultation.patient_id,
            "doctor_id": consultation.doctor_id,
            "slot_id": consultation.slot_id,
            "status": consultation.status,
            "notes": consultation.notes,
            "created_at": consultation.created_at.isoformat(),
            "updated_at": consultation.updated_at.isoformat(),
            "slot": {
                "id": slot.id,
                "doctor_id": slot.doctor_id,
                "start_at": slot.start_at.isoformat(),
                "end_at": slot.end_at.isoformat(),
                "status": slot.status,
            },
        }

        # 7. Persist Idempotency Record if key provided
        if idempotency_key:
            idemp_record = IdempotencyRecord(
                scope="bookings:create",
                key=idempotency_key,
                request_hash=req_hash,
                status_code=201,
                response_body=json.dumps(response_body),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add(idemp_record)

        # 8. Commit entire transaction atomically
        db.commit()
        return response_body, 201

    except (IntegrityError, OperationalError, StaleDataError) as ce:
        if db.is_active:
            try:
                db.rollback()
            except Exception:
                pass
        raise ConflictException(
            detail="This appointment slot is no longer available. It was reserved concurrently.",
            error_code="SLOT_ALREADY_RESERVED",
        ) from ce
    except AppException:
        if db.is_active:
            try:
                db.rollback()
            except Exception:
                pass
        raise
    except Exception:
        if db.is_active:
            try:
                db.rollback()
            except Exception:
                pass
        raise


def get_user_bookings(
    db: Session,
    user: User,
    page: int = 1,
    size: int = 20,
) -> Tuple[List[Consultation], int]:
    stmt = (
        select(Consultation)
        .options(joinedload(Consultation.slot))
        .order_by(Consultation.created_at.desc())
    )

    if user.role == "patient":
        stmt = stmt.where(Consultation.patient_id == user.id)
    elif user.role == "doctor":
        doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
        if not doctor:
            return [], 0
        stmt = stmt.where(Consultation.doctor_id == doctor.id)
    # Admin sees all bookings

    offset = (page - 1) * size
    results = db.scalars(stmt.offset(offset).limit(size)).unique().all()
    total = len(results)
    return list(results), total


def get_booking_details(db: Session, booking_id: str, user: User) -> Consultation:
    stmt = (
        select(Consultation)
        .options(joinedload(Consultation.slot))
        .where(Consultation.id == booking_id)
    )
    booking = db.scalar(stmt)
    if not booking:
        raise NotFoundException("Consultation", booking_id)

    # Ownership check
    if user.role == "patient" and booking.patient_id != user.id:
        raise ForbiddenException("You are not authorized to view this booking")
    elif user.role == "doctor":
        doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
        if not doctor or booking.doctor_id != doctor.id:
            raise ForbiddenException("You are not authorized to view this booking")

    return booking


def cancel_booking(
    db: Session,
    booking_id: str,
    user: User,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Consultation:
    booking = db.scalar(
        select(Consultation)
        .options(joinedload(Consultation.slot))
        .where(Consultation.id == booking_id)
        .with_for_update()
    )
    if not booking:
        raise NotFoundException("Consultation", booking_id)

    # Ownership validation
    if user.role == "patient" and booking.patient_id != user.id:
        raise ForbiddenException("You can only cancel your own bookings")
    elif user.role == "doctor":
        doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
        if not doctor or booking.doctor_id != doctor.id:
            raise ForbiddenException("You can only cancel consultations assigned to you")

    if booking.status != "SCHEDULED":
        raise ConflictException(
            detail=f"Cannot cancel a consultation with status '{booking.status}'",
            error_code="INVALID_STATE_TRANSITION"
        )

    # Transition states
    booking.status = "CANCELLED"
    if booking.slot:
        booking.slot.status = "AVAILABLE"  # Reopen slot for other patients

    # Create Outbox Event
    outbox_event = OutboxEvent(
        event_type="BOOKING_CANCELLED",
        payload=json.dumps({
            "consultation_id": booking.id,
            "patient_id": booking.patient_id,
            "doctor_id": booking.doctor_id,
            "reason": reason,
        }),
        status="PENDING",
    )
    db.add(outbox_event)

    record_audit_log(
        db=db,
        action="BOOKING_CANCELLED",
        resource_type="consultation",
        actor_id=user.id,
        resource_id=booking.id,
        ip_address=ip_address,
        details={"reason": reason},
    )

    db.commit()
    db.refresh(booking)
    return booking
