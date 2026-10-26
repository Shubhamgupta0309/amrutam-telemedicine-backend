from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.modules.bookings.models import Consultation
from app.modules.doctors.models import AvailabilitySlot


def create_booked_consultation(db: Session, patient_id: str, doctor_id: str) -> Consultation:
    now = datetime.now(timezone.utc) + timedelta(days=2)
    slot = AvailabilitySlot(
        doctor_id=doctor_id,
        start_at=now,
        end_at=now + timedelta(minutes=30),
        status="BOOKED"
    )
    db.add(slot)
    db.flush()

    consultation = Consultation(
        patient_id=patient_id,
        doctor_id=doctor_id,
        slot_id=slot.id,
        status="SCHEDULED",
        notes="Consultation test"
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)
    return consultation


def test_consultation_lifecycle_and_prescriptions(client: TestClient, db_session: Session, seed_users):
    patient1 = seed_users["patient_1"]
    patient2 = seed_users["patient_2"]
    doctor = seed_users["doctor"]
    doctor_profile = seed_users["doctor_profile"]

    patient1_token = create_access_token(subject=patient1.id, role="patient")
    patient2_token = create_access_token(subject=patient2.id, role="patient")
    doctor_token = create_access_token(subject=doctor.id, role="doctor")

    consultation = create_booked_consultation(db_session, patient1.id, doctor_profile.id)

    # 1. Start Consultation (Doctor only)
    start_res = client.post(
        f"/api/v1/consultations/{consultation.id}/start",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"notes": "Patient reports throat irritation"}
    )
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_PROGRESS"

    # Patient cannot start consultation -> 403 Forbidden
    patient_try_start = client.post(
        f"/api/v1/consultations/{consultation.id}/start",
        headers={"Authorization": f"Bearer {patient1_token}"},
        json={"notes": "Patient attempt"}
    )
    assert patient_try_start.status_code == 403

    # 2. Issue Prescription
    rx_payload = {
        "diagnosis": "Pharyngitis & Pitta Imbalance",
        "medications": [
            {
                "name": "Sitopaladi Churna",
                "dosage": "3g",
                "frequency": "Twice daily with honey",
                "duration": "5 days",
                "instructions": "Warm water after consumption"
            },
            {
                "name": "Khadiradi Vati",
                "dosage": "1 tablet",
                "frequency": "3 times daily",
                "duration": "5 days"
            }
        ],
        "instructions": "Avoid cold beverages, gargle with warm saline water twice daily."
    }
    rx_res = client.post(
        f"/api/v1/consultations/{consultation.id}/prescriptions",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json=rx_payload
    )
    assert rx_res.status_code == 201
    assert rx_res.json()["diagnosis"] == "Pharyngitis & Pitta Imbalance"

    # 3. Patient 1 (owner) can retrieve prescription
    p1_get = client.get(
        f"/api/v1/consultations/{consultation.id}/prescriptions",
        headers={"Authorization": f"Bearer {patient1_token}"}
    )
    assert p1_get.status_code == 200
    p1_rx = p1_get.json()
    assert len(p1_rx) == 1
    assert len(p1_rx[0]["medications"]) == 2

    # 4. Patient 2 (unauthorized) cannot access Patient 1's prescription -> 403 Forbidden
    p2_get = client.get(
        f"/api/v1/consultations/{consultation.id}/prescriptions",
        headers={"Authorization": f"Bearer {patient2_token}"}
    )
    assert p2_get.status_code == 403

    # 5. Complete Consultation
    comp_res = client.post(
        f"/api/v1/consultations/{consultation.id}/complete",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"final_notes": "Prescription issued, patient advised follow-up after 5 days."}
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"
