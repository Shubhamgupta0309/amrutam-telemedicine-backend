import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    DateTime,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base, utc_now


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_action_resource", "action", "resource_type"),
        Index("ix_audit_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    actor_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    request_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )  # JSON-encoded sanitized metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )
