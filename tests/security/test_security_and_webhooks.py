import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.bookings.models import Consultation
from app.modules.doctors.models import AvailabilitySlot
from app.modules.payments.models import Payment
from datetime import datetime, timedelta, timezone


def test_payment_webhook_hmac_and_deduplication(client: TestClient, db_session: Session, seed_users):
    # Setup consultation
    now = datetime.now(timezone.utc) + timedelta(days=4)
    slot = AvailabilitySlot(
        doctor_id=seed_users["doctor_profile"].id,
        start_at=now,
        end_at=now + timedelta(minutes=30),
        status="BOOKED"
    )
    db_session.add(slot)
    db_session.flush()

    consultation = Consultation(
        patient_id=seed_users["patient_1"].id,
        doctor_id=seed_users["doctor_profile"].id,
        slot_id=slot.id,
        status="SCHEDULED",
    )
    db_session.add(consultation)
    db_session.commit()

    webhook_data = {
        "event_id": "evt_test_123456",
        "consultation_id": consultation.id,
        "amount": 500.0,
        "currency": "INR",
        "status": "SUCCESS",
    }
    payload_bytes = json.dumps(webhook_data).encode("utf-8")

    # Generate valid HMAC signature
    valid_sig = hmac.new(
        settings.PAYMENT_WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    # 1. Invalid signature rejected with 401 Unauthorized
    bad_res = client.post(
        "/api/v1/payments/webhook",
        headers={"X-Signature": "forged_signature_here", "Content-Type": "application/json"},
        content=payload_bytes
    )
    assert bad_res.status_code == 401

    # 2. Valid signature accepted with 200 OK
    good_res = client.post(
        "/api/v1/payments/webhook",
        headers={"X-Signature": valid_sig, "Content-Type": "application/json"},
        content=payload_bytes
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "success"

    # 3. Duplicate event ID -> Idempotently handled
    dup_res = client.post(
        "/api/v1/payments/webhook",
        headers={"X-Signature": valid_sig, "Content-Type": "application/json"},
        content=payload_bytes
    )
    assert dup_res.status_code == 200
    assert dup_res.json()["status"] == "already_processed"


def test_health_and_metrics_endpoints(client: TestClient):
    # Liveness check
    live_res = client.get("/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    # Readiness check
    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"

    # Prometheus metrics
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "http_requests_total" in metrics_res.text


def test_patient_cannot_access_another_patients_booking(client: TestClient, db_session: Session, seed_users):
    from app.core.security import create_access_token

    # Setup booking for Patient 1
    now = datetime.now(timezone.utc) + timedelta(days=6)
    slot = AvailabilitySlot(
        doctor_id=seed_users["doctor_profile"].id,
        start_at=now,
        end_at=now + timedelta(minutes=30),
        status="BOOKED"
    )
    db_session.add(slot)
    db_session.flush()

    consultation = Consultation(
        patient_id=seed_users["patient_1"].id,
        doctor_id=seed_users["doctor_profile"].id,
        slot_id=slot.id,
        status="SCHEDULED",
    )
    db_session.add(consultation)
    db_session.commit()

    patient1_token = create_access_token(subject=seed_users["patient_1"].id, role="patient")
    patient2_token = create_access_token(subject=seed_users["patient_2"].id, role="patient")

    # Patient 1 can access
    res1 = client.get(
        f"/api/v1/bookings/{consultation.id}",
        headers={"Authorization": f"Bearer {patient1_token}"}
    )
    assert res1.status_code == 200

    # Patient 2 is rejected with 403 Forbidden
    res2 = client.get(
        f"/api/v1/bookings/{consultation.id}",
        headers={"Authorization": f"Bearer {patient2_token}"}
    )
    assert res2.status_code == 403
    assert res2.json()["error_code"] == "FORBIDDEN"


def test_rate_limiter_throttles_excessive_traffic(client: TestClient):
    from app.main import RATE_LIMIT_BUCKET
    # Clear bucket for clean test
    RATE_LIMIT_BUCKET.clear()

    # Issue 60 allowed requests
    for _ in range(60):
        res = client.get("/api/v1/doctors")
        assert res.status_code in (200, 401, 403)

    # 61st request should be throttled
    blocked_res = client.get("/api/v1/doctors")
    assert blocked_res.status_code == 429
    assert blocked_res.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
    RATE_LIMIT_BUCKET.clear()

