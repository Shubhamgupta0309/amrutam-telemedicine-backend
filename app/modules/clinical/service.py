import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.modules.audit.service import record_audit_log
from app.modules.bookings.models import Consultation, OutboxEvent
from app.modules.clinical.models import Prescription
from app.modules.clinical.schemas import MedicationItem, PrescriptionCreate
from app.modules.doctors.models import Doctor
from app.modules.users.models import User


def start_consultation(
    db: Session,
    consultation_id: str,
    doctor_user: User,
    notes: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Consultation:
    consultation = db.scalar(select(Consultation).where(Consultation.id == consultation_id))
    if not consultation:
        raise NotFoundException("Consultation", consultation_id)

    doctor = db.scalar(select(Doctor).where(Doctor.user_id == doctor_user.id))
    if not doctor or consultation.doctor_id != doctor.id:
        raise ForbiddenException("Only the designated doctor can start this consultation")

    if consultation.status != "SCHEDULED":
        raise ConflictException(
            detail=f"Cannot start consultation with status '{consultation.status}'",
            error_code="INVALID_STATUS_TRANSITION"
        )

    consultation.status = "IN_PROGRESS"
    if notes:
        consultation.notes = (consultation.notes or "") + f"\nStart notes: {notes}"

    # Outbox event
    db.add(OutboxEvent(
        event_type="CONSULTATION_STARTED",
        payload=json.dumps({"consultation_id": consultation.id}),
        status="PENDING",
    ))

    record_audit_log(
        db=db,
        action="CONSULTATION_STARTED",
        resource_type="consultation",
        actor_id=doctor_user.id,
        resource_id=consultation.id,
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(consultation)
    return consultation


def complete_consultation(
    db: Session,
    consultation_id: str,
    doctor_user: User,
    final_notes: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Consultation:
    consultation = db.scalar(select(Consultation).where(Consultation.id == consultation_id))
    if not consultation:
        raise NotFoundException("Consultation", consultation_id)

    doctor = db.scalar(select(Doctor).where(Doctor.user_id == doctor_user.id))
    if not doctor or consultation.doctor_id != doctor.id:
        raise ForbiddenException("Only the designated doctor can complete this consultation")

    if consultation.status != "IN_PROGRESS":
        raise ConflictException(
            detail=f"Cannot complete consultation from status '{consultation.status}' (must be IN_PROGRESS)",
            error_code="INVALID_STATUS_TRANSITION"
        )

    consultation.status = "COMPLETED"
    if final_notes:
        consultation.notes = (consultation.notes or "") + f"\nFinal notes: {final_notes}"

    db.add(OutboxEvent(
        event_type="CONSULTATION_COMPLETED",
        payload=json.dumps({
            "consultation_id": consultation.id,
            "patient_id": consultation.patient_id,
            "doctor_id": consultation.doctor_id,
        }),
        status="PENDING",
    ))

    record_audit_log(
        db=db,
        action="CONSULTATION_COMPLETED",
        resource_type="consultation",
        actor_id=doctor_user.id,
        resource_id=consultation.id,
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(consultation)
    return consultation


def issue_prescription(
    db: Session,
    consultation_id: str,
    doctor_user: User,
    prescription_data: PrescriptionCreate,
    ip_address: Optional[str] = None,
) -> Prescription:
    consultation = db.scalar(select(Consultation).where(Consultation.id == consultation_id))
    if not consultation:
        raise NotFoundException("Consultation", consultation_id)

    doctor = db.scalar(select(Doctor).where(Doctor.user_id == doctor_user.id))
    if not doctor or consultation.doctor_id != doctor.id:
        raise ForbiddenException("Only the assigned doctor can issue prescriptions for this consultation")

    if doctor.verification_status != "VERIFIED":
        raise ForbiddenException("Only verified doctors can issue prescriptions")

    if consultation.status not in ["IN_PROGRESS", "COMPLETED"]:
        raise ConflictException(
            detail=f"Prescriptions can only be issued during or after consultation (current: {consultation.status})",
            error_code="INVALID_CONSULTATION_STATE"
        )

    # Check if prescription already issued
    existing = db.scalar(select(Prescription).where(Prescription.consultation_id == consultation_id))
    if existing:
        raise ConflictException("A prescription has already been issued for this consultation")

    # Serialize medications
    meds_json = json.dumps([m.model_dump() for m in prescription_data.medications])

    prescription = Prescription(
        consultation_id=consultation.id,
        doctor_id=doctor.id,
        patient_id=consultation.patient_id,
        diagnosis=prescription_data.diagnosis,
        medications=meds_json,
        instructions=prescription_data.instructions,
    )
    db.add(prescription)

    db.add(OutboxEvent(
        event_type="PRESCRIPTION_ISSUED",
        payload=json.dumps({
            "prescription_id": prescription.id,
            "consultation_id": consultation.id,
            "patient_id": consultation.patient_id,
        }),
        status="PENDING",
    ))

    record_audit_log(
        db=db,
        action="PRESCRIPTION_ISSUED",
        resource_type="prescription",
        actor_id=doctor_user.id,
        resource_id=prescription.id,
        ip_address=ip_address,
        details={"consultation_id": consultation.id},
    )

    db.commit()
    db.refresh(prescription)
    return prescription


def get_consultation_prescriptions(
    db: Session,
    consultation_id: str,
    user: User,
) -> List[Dict[str, Any]]:
    consultation = db.scalar(select(Consultation).where(Consultation.id == consultation_id))
    if not consultation:
        raise NotFoundException("Consultation", consultation_id)

    # Authorization Check
    if user.role == "patient" and consultation.patient_id != user.id:
        raise ForbiddenException("You are not authorized to access this prescription")
    elif user.role == "doctor":
        doctor = db.scalar(select(Doctor).where(Doctor.user_id == user.id))
        if not doctor or consultation.doctor_id != doctor.id:
            raise ForbiddenException("You are not authorized to access this prescription")

    prescriptions = list(
        db.scalars(select(Prescription).where(Prescription.consultation_id == consultation_id)).all()
    )

    result = []
    for p in prescriptions:
        result.append({
            "id": p.id,
            "consultation_id": p.consultation_id,
            "doctor_id": p.doctor_id,
            "patient_id": p.patient_id,
            "diagnosis": p.diagnosis,
            "medications": json.loads(p.medications),
            "instructions": p.instructions,
            "created_at": p.created_at,
        })
    return result
