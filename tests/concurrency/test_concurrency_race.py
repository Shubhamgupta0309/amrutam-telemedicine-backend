import concurrent.futures
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import create_access_token
from app.modules.bookings.models import Consultation
from app.modules.doctors.models import AvailabilitySlot


def test_concurrent_booking_attempts_prevent_double_booking(client: TestClient, db_session: Session, seed_users):
    """
    Race condition test:
    Two patients simultaneously attempt to reserve the exact same availability slot.
    The system must guarantee that exactly one patient succeeds, and the other receives a 409 Conflict.
    """
    patient1_token = create_access_token(subject=seed_users["patient_1"].id, role="patient")
    patient2_token = create_access_token(subject=seed_users["patient_2"].id, role="patient")
    doctor_profile = seed_users["doctor_profile"]

    now = datetime.now(timezone.utc) + timedelta(days=5)
    slot = AvailabilitySlot(
        doctor_id=doctor_profile.id,
        start_at=now,
        end_at=now + timedelta(minutes=30),
        status="AVAILABLE"
    )
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)

    results = []

    def book_slot(token: str, patient_name: str):
        resp = client.post(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "doctor_id": doctor_profile.id,
                "slot_id": slot.id,
                "notes": f"Booked by {patient_name}"
            }
        )
        return resp.status_code, resp.json()

    # Dispatch both requests concurrently in parallel threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(book_slot, patient1_token, "Patient 1")
        f2 = executor.submit(book_slot, patient2_token, "Patient 2")
        results = [f1.result(), f2.result()]

    status_codes = [r[0] for r in results]

    # Exactly ONE must succeed (201) and ONE must fail with conflict (409)
    assert 201 in status_codes, f"Expected one 201 success, got {status_codes}"
    assert 409 in status_codes, f"Expected one 409 conflict, got {status_codes}"
