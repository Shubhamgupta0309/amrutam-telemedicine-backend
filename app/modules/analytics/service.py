from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Consultation
from app.modules.clinical.models import Prescription
from app.modules.doctors.models import Doctor
from app.modules.payments.models import Payment
from app.modules.users.models import User


def get_admin_analytics(db: Session) -> dict:
    total_consultations = db.scalar(select(func.count(Consultation.id))) or 0
    scheduled = db.scalar(
        select(func.count(Consultation.id)).where(Consultation.status == "SCHEDULED")
    ) or 0
    in_progress = db.scalar(
        select(func.count(Consultation.id)).where(Consultation.status == "IN_PROGRESS")
    ) or 0
    completed = db.scalar(
        select(func.count(Consultation.id)).where(Consultation.status == "COMPLETED")
    ) or 0
    cancelled = db.scalar(
        select(func.count(Consultation.id)).where(Consultation.status == "CANCELLED")
    ) or 0

    total_patients = db.scalar(
        select(func.count(User.id)).where(User.role == "patient")
    ) or 0
    total_doctors = db.scalar(select(func.count(Doctor.id))) or 0
    verified_doctors = db.scalar(
        select(func.count(Doctor.id)).where(Doctor.verification_status == "VERIFIED")
    ) or 0

    total_prescriptions = db.scalar(select(func.count(Prescription.id))) or 0

    total_revenue = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(Payment.status == "SUCCESS")
    ) or 0.0

    return {
        "total_consultations": total_consultations,
        "scheduled_consultations": scheduled,
        "in_progress_consultations": in_progress,
        "completed_consultations": completed,
        "cancelled_consultations": cancelled,
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "verified_doctors": verified_doctors,
        "total_prescriptions": total_prescriptions,
        "total_revenue": float(total_revenue),
    }
