import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.users.models import User
    from app.modules.bookings.models import Consultation


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    specialty: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    registration_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True
    )  # PENDING, VERIFIED, REJECTED
    consultation_fee: Mapped[float] = mapped_column(
        Float,
        default=500.0,
        nullable=False
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="doctor_profile")
    availability_slots: Mapped[List["AvailabilitySlot"]] = relationship(
        "AvailabilitySlot",
        back_populates="doctor",
        cascade="all, delete-orphan",
        order_by="AvailabilitySlot.start_at"
    )
    consultations: Mapped[List["Consultation"]] = relationship(
        "Consultation",
        foreign_keys="Consultation.doctor_id",
        back_populates="doctor"
    )


class AvailabilitySlot(Base, TimestampMixin):
    __tablename__ = "availability_slots"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="check_slot_end_after_start"),
        Index("ix_doctor_slot_search", "doctor_id", "status", "start_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="AVAILABLE",
        nullable=False,
        index=True
    )  # AVAILABLE, RESERVED, BOOKED, CANCELLED

    # Relationships
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="availability_slots")
    consultation: Mapped[Optional["Consultation"]] = relationship(
        "Consultation",
        back_populates="slot",
        uselist=False
    )
