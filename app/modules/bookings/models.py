import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.modules.users.models import User
    from app.modules.doctors.models import Doctor, AvailabilitySlot
    from app.modules.clinical.models import Prescription
    from app.modules.payments.models import Payment


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"
    __table_args__ = (
        Index("ix_consultation_patient_status", "patient_id", "status"),
        Index("ix_consultation_doctor_status", "doctor_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    slot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("availability_slots.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="SCHEDULED",
        nullable=False,
        index=True
    )  # SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    patient: Mapped["User"] = relationship(
        "User",
        foreign_keys=[patient_id],
        back_populates="consultations_as_patient"
    )
    doctor: Mapped["Doctor"] = relationship(
        "Doctor",
        foreign_keys=[doctor_id],
        back_populates="consultations"
    )
    slot: Mapped["AvailabilitySlot"] = relationship(
        "AvailabilitySlot",
        back_populates="consultation"
    )
    prescription: Mapped[Optional["Prescription"]] = relationship(
        "Prescription",
        back_populates="consultation",
        uselist=False,
        cascade="all, delete-orphan"
    )
    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment",
        back_populates="consultation",
        uselist=False,
        cascade="all, delete-orphan"
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
        Index("ix_idempotency_scope_key", "scope", "key"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    response_body: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    payload: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True
    )  # PENDING, PROCESSED, FAILED
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
