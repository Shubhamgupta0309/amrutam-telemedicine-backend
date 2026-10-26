from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.core.security import create_access_token


def test_doctor_slot_creation_and_overlap_rejection(client: TestClient, seed_users):
    doctor = seed_users["doctor"]
    doc_profile = seed_users["doctor_profile"]
    doc_token = create_access_token(subject=doctor.id, role="doctor")

    now = datetime.now(timezone.utc) + timedelta(days=1)
    slot1_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    slot1_end = now.replace(hour=10, minute=30, second=0, microsecond=0)

    # 1. Successful slot creation
    res = client.post(
        f"/api/v1/doctors/{doc_profile.id}/availability",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"start_at": slot1_start.isoformat(), "end_at": slot1_end.isoformat()}
    )
    assert res.status_code == 201
    assert res.json()["status"] == "AVAILABLE"

    # 2. Overlapping slot rejected with 409 Conflict
    overlap_start = now.replace(hour=10, minute=15, second=0, microsecond=0)
    overlap_end = now.replace(hour=10, minute=45, second=0, microsecond=0)
    overlap_res = client.post(
        f"/api/v1/doctors/{doc_profile.id}/availability",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"start_at": overlap_start.isoformat(), "end_at": overlap_end.isoformat()}
    )
    assert overlap_res.status_code == 409
    assert overlap_res.json()["error_code"] == "SLOT_OVERLAP_CONFLICT"

    # 3. Invalid times: end_at <= start_at rejected with 422
    bad_time_res = client.post(
        f"/api/v1/doctors/{doc_profile.id}/availability",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"start_at": slot1_end.isoformat(), "end_at": slot1_start.isoformat()}
    )
    assert bad_time_res.status_code == 422


def test_unverified_doctor_cannot_create_slots(client: TestClient, seed_users):
    unverified = seed_users["unverified_doctor"]
    doc_profile_2 = seed_users["unverified_doctor"].doctor_profile
    token = create_access_token(subject=unverified.id, role="doctor")

    now = datetime.now(timezone.utc) + timedelta(days=2)
    res = client.post(
        f"/api/v1/doctors/doctor-profile-2/availability",
        headers={"Authorization": f"Bearer {token}"},
        json={"start_at": now.isoformat(), "end_at": (now + timedelta(minutes=30)).isoformat()}
    )
    assert res.status_code == 403


def test_doctor_search_and_specialty_filter(client: TestClient, seed_users):
    # Search Ayurveda
    res = client.get("/api/v1/doctors?specialty=Ayurveda")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["specialty"] == "Ayurveda"
    assert data["items"][0]["verification_status"] == "VERIFIED"
