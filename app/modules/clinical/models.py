import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.bookings.models import Consultation
    from app.modules.doctors.models import Doctor
    from app.modules.users.models import User


class Prescription(Base, TimestampMixin):
    __tablename__ = "prescriptions"
    __table_args__ = (
        Index("ix_prescription_patient", "patient_id"),
        Index("ix_prescription_doctor", "doctor_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    consultation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    diagnosis: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    medications: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )  # JSON-encoded list of medication objects
    instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    consultation: Mapped["Consultation"] = relationship(
        "Consultation",
        back_populates="prescription"
    )
    doctor: Mapped["Doctor"] = relationship(
        "Doctor",
        foreign_keys=[doctor_id]
    )
    patient: Mapped["User"] = relationship(
        "User",
        foreign_keys=[patient_id]
    )
