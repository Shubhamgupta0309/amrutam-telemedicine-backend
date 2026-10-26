import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.doctors.models import Doctor
from app.modules.users.models import Profile, User

# In-memory SQLite for high-speed, isolated test runs
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_users(db_session: Session):
    pwd_hash = get_password_hash("Password123!")

    # Patient 1
    p1 = User(id="patient-1-uuid", email="patient1@example.com", password_hash=pwd_hash, role="patient", status="active")
    p1_prof = Profile(id="p1-prof", user_id=p1.id, name="Patient One", timezone="UTC")

    # Patient 2
    p2 = User(id="patient-2-uuid", email="patient2@example.com", password_hash=pwd_hash, role="patient", status="active")
    p2_prof = Profile(id="p2-prof", user_id=p2.id, name="Patient Two", timezone="UTC")

    # Verified Doctor
    doc_user = User(id="doctor-1-uuid", email="dr.sharma@amrutam.co.in", password_hash=pwd_hash, role="doctor", status="active")
    doc_prof = Profile(id="doc1-prof", user_id=doc_user.id, name="Dr. Sharma", timezone="Asia/Kolkata")
    doctor_entry = Doctor(
        id="doctor-profile-1",
        user_id=doc_user.id,
        specialty="Ayurveda",
        registration_number="AYU-12345",
        verification_status="VERIFIED",
        consultation_fee=500.0,
    )

    # Unverified Doctor
    unverified_user = User(id="doctor-2-uuid", email="dr.unverified@amrutam.co.in", password_hash=pwd_hash, role="doctor", status="active")
    unverified_doc = Doctor(
        id="doctor-profile-2",
        user_id=unverified_user.id,
        specialty="Dermatology",
        registration_number="DERM-99999",
        verification_status="PENDING",
        consultation_fee=600.0,
    )

    # Admin
    admin_user = User(id="admin-uuid", email="admin@example.com", password_hash=pwd_hash, role="admin", status="active")

    db_session.add_all([p1, p1_prof, p2, p2_prof, doc_user, doc_prof, doctor_entry, unverified_user, unverified_doc, admin_user])
    db_session.commit()

    return {
        "patient_1": p1,
        "patient_2": p2,
        "doctor": doc_user,
        "doctor_profile": doctor_entry,
        "unverified_doctor": unverified_user,
        "admin": admin_user,
    }
