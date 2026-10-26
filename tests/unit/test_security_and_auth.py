import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import create_access_token, verify_password
from app.modules.audit.models import AuditLog
from app.modules.users.models import User


def test_user_registration_and_login(client: TestClient):
    # 1. Register Patient
    reg_payload = {
        "email": "newpatient@example.com",
        "password": "SecurePassword123!",
        "name": "New Patient",
        "role": "patient",
        "phone": "+919876543210",
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "newpatient@example.com"
    assert data["role"] == "patient"

    # 2. Duplicate registration rejected with 409 Conflict
    dup_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409
    assert dup_res.json()["error_code"] == "CONFLICT"

    # 3. Successful Login
    login_res = client.post("/api/v1/auth/login", json={
        "email": "newpatient@example.com",
        "password": "SecurePassword123!",
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    assert login_data["role"] == "patient"

    # 4. Invalid Password rejected with 401 Unauthorized
    bad_login = client.post("/api/v1/auth/login", json={
        "email": "newpatient@example.com",
        "password": "WrongPassword!",
    })
    assert bad_login.status_code == 401
    assert bad_login.json()["error_code"] == "UNAUTHORIZED"


def test_admin_endpoints_reject_ordinary_users(client: TestClient, seed_users):
    patient_token = create_access_token(subject=seed_users["patient_1"].id, role="patient")
    doctor_token = create_access_token(subject=seed_users["doctor"].id, role="doctor")
    admin_token = create_access_token(subject=seed_users["admin"].id, role="admin")

    # Patient attempt on Admin Analytics -> 403 Forbidden
    res1 = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {patient_token}"})
    assert res1.status_code == 403

    # Doctor attempt on Admin Analytics -> 403 Forbidden
    res2 = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res2.status_code == 403

    # Admin attempt -> 200 OK
    res3 = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {admin_token}"})
    assert res3.status_code == 200
    assert "total_consultations" in res3.json()


def test_audit_logs_redact_sensitive_information(client: TestClient, db_session: Session):
    reg_payload = {
        "email": "audit_test@example.com",
        "password": "SuperSecretPassword123!",
        "name": "Audit Test",
        "role": "patient",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    # Inspect audit_logs in DB
    logs = list(db_session.scalars(select(AuditLog)).all())
    assert len(logs) > 0
    for log in logs:
        if log.details:
            # Must NOT contain the plaintext password or password_hash
            assert "SuperSecretPassword123!" not in log.details
            assert "password_hash" not in log.details
