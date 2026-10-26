# Import all models for Alembic and SQLAlchemy metadata
from app.db.base_class import Base
from app.modules.users.models import User, Profile
from app.modules.doctors.models import Doctor, AvailabilitySlot
from app.modules.bookings.models import Consultation, IdempotencyRecord, OutboxEvent
from app.modules.clinical.models import Prescription
from app.modules.payments.models import Payment
from app.modules.audit.models import AuditLog

__all__ = [
    "Base",
    "User",
    "Profile",
    "Doctor",
    "AvailabilitySlot",
    "Consultation",
    "IdempotencyRecord",
    "OutboxEvent",
    "Prescription",
    "Payment",
    "AuditLog",
]
