from typing import Optional
from pydantic import BaseModel, Field


class PaymentWebhookPayload(BaseModel):
    event_id: str = Field(..., description="Unique payment provider event ID")
    consultation_id: str
    amount: float
    currency: str = "INR"
    status: str = Field(..., description="SUCCESS or FAILED")
    payment_method: Optional[str] = "card"


class PaymentCreateIntent(BaseModel):
    consultation_id: str
    amount: float
    currency: str = "INR"


class PaymentIntentResponse(BaseModel):
    payment_id: str
    consultation_id: str
    amount: float
    currency: str
    client_secret: str
    status: str
