import hmac
import hashlib
import json
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from app.modules.audit.service import record_audit_log
from app.modules.bookings.models import Consultation, OutboxEvent
from app.modules.payments.models import Payment
from app.modules.payments.schemas import PaymentCreateIntent, PaymentWebhookPayload


def verify_webhook_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """Validate webhook HMAC SHA256 signature."""
    if not signature_header:
        return False

    expected_sig = hmac.new(
        settings.PAYMENT_WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature_header)


def create_payment_intent(
    db: Session,
    intent_data: PaymentCreateIntent,
    user_id: str,
) -> Payment:
    consultation = db.scalar(select(Consultation).where(Consultation.id == intent_data.consultation_id))
    if not consultation:
        raise NotFoundException("Consultation", intent_data.consultation_id)

    payment = Payment(
        consultation_id=intent_data.consultation_id,
        amount=intent_data.amount,
        currency=intent_data.currency,
        status="PENDING",
        provider="mock_pay",
        provider_reference=f"mock_intent_{uuid.uuid4().hex[:12]}",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def process_payment_webhook(
    db: Session,
    data: PaymentWebhookPayload,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    # Deduplication check: Has this provider event ID already been recorded?
    existing_payment = db.scalar(
        select(Payment).where(Payment.provider_reference == data.event_id)
    )
    if existing_payment:
        # Idempotent webhook response
        return {
            "status": "already_processed",
            "payment_id": existing_payment.id,
            "provider_reference": data.event_id,
        }

    # Verify consultation exists
    consultation = db.scalar(select(Consultation).where(Consultation.id == data.consultation_id))
    if not consultation:
        raise NotFoundException("Consultation", data.consultation_id)

    # Record payment
    payment = Payment(
        consultation_id=data.consultation_id,
        amount=data.amount,
        currency=data.currency,
        status=data.status,
        provider="mock_pay",
        provider_reference=data.event_id,
    )
    db.add(payment)

    # Add outbox event
    db.add(OutboxEvent(
        event_type="PAYMENT_PROCESSED",
        payload=json.dumps({
            "payment_id": payment.id,
            "consultation_id": data.consultation_id,
            "status": data.status,
            "amount": data.amount,
        }),
        status="PENDING",
    ))

    # Audit log (zero sensitive payment data)
    record_audit_log(
        db=db,
        action="PAYMENT_WEBHOOK_PROCESSED",
        resource_type="payment",
        resource_id=payment.id,
        ip_address=ip_address,
        details={
            "consultation_id": data.consultation_id,
            "status": data.status,
            "event_id": data.event_id,
        },
    )

    db.commit()
    return {
        "status": "success",
        "payment_id": payment.id,
        "provider_reference": data.event_id,
    }
