"""
Database Reset & Demo Seeding Utility
Wipes transactional demo data and re-seeds pristine accounts and slots.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.modules.users.models import User, Profile
from app.modules.doctors.models import Doctor, AvailabilitySlot
from app.core.security import get_password_hash


def reset_database():
    db = SessionLocal()
    print("Resetting database tables...")
    try:
        # Wipe in correct foreign key order
        for table in [
            "prescriptions",
            "payments",
            "consultations",
            "idempotency_records",
            "outbox_events",
            "audit_logs",
            "availability_slots",
            "doctors",
            "profiles",
            "users",
        ]:
            db.execute(text(f"DELETE FROM {table};"))
        db.commit()
        print("All existing records cleared.")

        # 1. Seed Admin
        admin = User(
            id="a0000000-0000-0000-0000-000000000001",
            email="admin@amrutam.co.in",
            password_hash=get_password_hash("Admin@Amrutam2026!"),
            role="admin",
            status="active",
            mfa_enabled=False,
        )
        db.add(admin)
        db.flush()
        db.add(Profile(user_id=admin.id, name="Amrutam Administrator", timezone="Asia/Kolkata"))

        # 2. Seed Patient
        patient = User(
            id="a0000000-0000-0000-0000-000000000002",
            email="patient@amrutam.co.in",
            password_hash=get_password_hash("Patient@Amrutam2026!"),
            role="patient",
            status="active",
            mfa_enabled=False,
        )
        db.add(patient)
        db.flush()
        db.add(Profile(user_id=patient.id, name="Rahul Sharma (Patient)", timezone="Asia/Kolkata"))

        # 3. Seed Doctor
        doctor_user = User(
            id="a0000000-0000-0000-0000-000000000003",
            email="doctor@amrutam.co.in",
            password_hash=get_password_hash("Doctor@Amrutam2026!"),
            role="doctor",
            status="active",
            mfa_enabled=False,
        )
        db.add(doctor_user)
        db.flush()
        db.add(Profile(user_id=doctor_user.id, name="Dr. Rajesh Varma", timezone="Asia/Kolkata"))
        db.flush()

        doctor = Doctor(
            id="e4be41f3-13f1-46d5-8280-93cc5f56a2c9",
            user_id=doctor_user.id,
            specialty="Ayurveda",
            registration_number="AYUR-IN-2024-9988",
            verification_status="VERIFIED",
            consultation_fee=500.0,
            bio="Senior Ayurvedic Consultant with 12+ years of clinical experience in Panchakarma.",
        )
        db.add(doctor)
        db.flush()

        # 4. Seed Slots for Tomorrow with fixed IDs
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        slots = [
            AvailabilitySlot(
                id="126c9a40-d75c-44a7-88a2-d5d73fb751f3",
                doctor_id=doctor.id,
                start_at=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
                end_at=tomorrow.replace(hour=10, minute=30, second=0, microsecond=0),
                status="AVAILABLE",
            ),
            AvailabilitySlot(
                id="68e49115-92c5-4dad-a9cb-4e20933a45f7",
                doctor_id=doctor.id,
                start_at=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
                end_at=tomorrow.replace(hour=11, minute=30, second=0, microsecond=0),
                status="AVAILABLE",
            ),
            AvailabilitySlot(
                id="e23f122c-8aa1-4c27-9962-937d1c14e492",
                doctor_id=doctor.id,
                start_at=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
                end_at=tomorrow.replace(hour=14, minute=30, second=0, microsecond=0),
                status="AVAILABLE",
            ),
        ]
        db.add_all(slots)
        db.commit()

        print("\nDatabase reset and seeded successfully!")
        print("==================================================")
        print("Admin:   admin@amrutam.co.in   | Admin@Amrutam2026!")
        print("Patient: patient@amrutam.co.in | Patient@Amrutam2026!")
        print("Doctor:  doctor@amrutam.co.in  | Doctor@Amrutam2026!")
        print(f"Doctor ID: {doctor.id}")
        print("Slots available: 3 (IDs: 126c9a40-..., 68e49115-..., e23f122c-...)")
        print("==================================================")
    except Exception as e:
        db.rollback()
        print(f"Error resetting database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    reset_database()
