import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import create_access_token
from app.modules.bookings.models import Consultation, OutboxEvent
from app.modules.doctors.models import AvailabilitySlot


def create_test_slot(db: Session, doctor_id: str) -> AvailabilitySlot:
    now = datetime.now(timezone.utc) + timedelta(days=3)
    slot = AvailabilitySlot(
        doctor_id=doctor_id,
        start_at=now,
        end_at=now + timedelta(minutes=30),
        status="AVAILABLE"
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def test_booking_idempotency_and_duplicate_handling(client: TestClient, db_session: Session, seed_users):
    patient_token = create_access_token(subject=seed_users["patient_1"].id, role="patient")
    doctor_profile = seed_users["doctor_profile"]
    slot = create_test_slot(db_session, doctor_profile.id)

    idempotency_key = f"key_{uuid.uuid4().hex}"
    booking_payload = {
        "doctor_id": doctor_profile.id,
        "slot_id": slot.id,
        "notes": "Severe headache and fever"
    }

    # 1. Initial booking request
    res1 = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {patient_token}", "Idempotency-Key": idempotency_key},
        json=booking_payload
    )
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["status"] == "SCHEDULED"
    assert data1["slot"]["status"] == "BOOKED"

    # Verify Outbox event was created atomically
    outbox = db_session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "BOOKING_CONFIRMED")
    )
    assert outbox is not None
    assert outbox.status == "PENDING"

    # 2. Repeated request with SAME key and SAME payload -> Returns original outcome
    res2 = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {patient_token}", "Idempotency-Key": idempotency_key},
        json=booking_payload
    )
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["id"] == data1["id"]

    # 3. Repeated request with SAME key and DIFFERENT payload -> 409 Conflict
    mismatched_payload = {
        "doctor_id": doctor_profile.id,
        "slot_id": slot.id,
        "notes": "Changed notes completely"
    }
    res3 = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {patient_token}", "Idempotency-Key": idempotency_key},
        json=mismatched_payload
    )
    assert res3.status_code == 409
    assert res3.json()["error_code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"


def test_booking_cancellation_releases_slot(client: TestClient, db_session: Session, seed_users):
    patient_token = create_access_token(subject=seed_users["patient_1"].id, role="patient")
    doctor_profile = seed_users["doctor_profile"]
    slot = create_test_slot(db_session, doctor_profile.id)

    # Book slot
    book_res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"doctor_id": doctor_profile.id, "slot_id": slot.id, "notes": "Fever"}
    )
    assert book_res.status_code == 201
    booking_id = book_res.json()["id"]

    # Cancel booking
    cancel_res = client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"reason": "Recovered already"}
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Slot must be back to AVAILABLE
    db_session.expire_all()
    reloaded_slot = db_session.scalar(select(AvailabilitySlot).where(AvailabilitySlot.id == slot.id))
    assert reloaded_slot.status == "AVAILABLE"
