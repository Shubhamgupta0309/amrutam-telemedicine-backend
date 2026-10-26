import json
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedException
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.payments import service
from app.modules.payments.schemas import PaymentCreateIntent, PaymentIntentResponse, PaymentWebhookPayload
from app.modules.users.models import User

router = APIRouter(prefix="/payments", tags=["Payments & Webhooks"])


@router.post("/create-intent", response_model=PaymentIntentResponse)
def create_payment(
    data: PaymentCreateIntent,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a payment intent for a consultation."""
    payment = service.create_payment_intent(db=db, intent_data=data, user_id=current_user.id)
    return {
        "payment_id": payment.id,
        "consultation_id": payment.consultation_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "client_secret": f"mock_secret_{payment.id}",
        "status": payment.status,
    }


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def payment_webhook(
    request: Request,
    x_signature: str = Header(None, alias="X-Signature"),
    db: Session = Depends(get_db),
):
    """
    Process verified payment provider webhook events.
    Verifies HMAC signature and prevents duplicate processing with event ID deduplication.
    """
    body_bytes = await request.body()
    if not service.verify_webhook_signature(body_bytes, x_signature):
        raise UnauthorizedException(detail="Invalid or missing webhook signature")

    payload_json = json.loads(body_bytes.decode("utf-8"))
    payload = PaymentWebhookPayload(**payload_json)

    client_ip = request.client.host if request.client else None
    return service.process_payment_webhook(
        db=db,
        data=payload,
        ip_address=client_ip,
    )
