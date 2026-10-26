# Five-Minute Video Demo Script & Walkthrough

This script provides a precise, minute-by-minute guide for recording the 5-minute evaluation demonstration for the **Amrutam Telemedicine Backend**.

---

## Timeline & Scene Progression

```
[0:00 - 0:40] Introduction & Architecture Overview
[0:40 - 1:25] Authentication, RBAC & MFA Verification
[1:25 - 2:25] Doctor Availability & Idempotent Booking Flow
[2:25 - 3:20] Consultation Lifecycle & Prescription Access Controls
[3:20 - 4:15] Concurrency Protection, Race Conditions & Automated Tests
[4:15 - 5:00] Observability, Metrics, Threat Model & Submission Wrap-Up
```

---

### Segment 1 [0:00 – 0:40]: Introduction and Architecture

* **Visual**:
  - Show the Git repository root on GitHub / local IDE.
  - Open Swagger UI at `http://localhost:8000/docs`.
  - Display the high-level architecture diagram in `docs/architecture.md`.
* **Narrative**:
  > *"Welcome to the demonstration of the production-grade Amrutam Telemedicine Backend. Built as a high-reliability modular monolith using Python, FastAPI, SQLAlchemy 2.0, PostgreSQL, and Alembic, this backend is architected to comfortably sustain over 100,000 daily consultations with sub-80ms p95 latencies. Our modular design clearly separates Authentication, Doctor Availability, Bookings, Clinical Prescriptions, Payments, and Audit Logging with strict ACID transaction boundaries."*

---

### Segment 2 [0:40 – 1:25]: Authentication, RBAC & Privileged Controls

* **Visual**:
  - In Swagger UI (`/docs`) or cURL / Postman:
  - Call `POST /api/v1/auth/register` to register a new patient.
  - Call `POST /api/v1/auth/login` to obtain a JWT bearer access token.
  - Attempt to access the admin endpoint `GET /api/v1/admin/analytics` with the patient token -> show `403 Forbidden`.
  - Authorize with the seeded Admin account -> show `200 OK` with operational analytics.
* **Narrative**:
  > *"Authentication enforces Argon2id password hashing and short-lived JWT access tokens. Server-side role-based access control strictly isolates patients, doctors, and administrators. Notice how accessing administrative analytics with a patient token immediately triggers a 403 Forbidden, but authenticating as an admin immediately reveals system telemetry."*

---

### Segment 3 [1:25 – 2:25]: Doctor Availability & Idempotent Booking

* **Visual**:
  - Call `GET /api/v1/doctors?specialty=Ayurveda` -> show doctor profiles.
  - Call `GET /api/v1/doctors/{id}/availability` -> show available time slots.
  - Call `POST /api/v1/bookings` with header `Idempotency-Key: demo-key-101` -> show `201 Created` with status `SCHEDULED`.
  - Re-send the exact same request with the same `Idempotency-Key` -> show that the cached `201 Created` is returned and **no duplicate booking or slot reservation is made**.
  - Modify the payload (e.g. change notes) with the same key -> show `409 Conflict: IDEMPOTENCY_PAYLOAD_MISMATCH`.
* **Narrative**:
  > *"Patients can filter verified doctors by specialty and query upcoming slots. In our booking flow, reliability is paramount: we require an Idempotency-Key header. Notice that submitting the identical request replays the original response instantly without creating duplicate records. Changing the payload while reusing the key triggers a 409 Conflict, defending against payload tampering."*

---

### Segment 4 [2:25 – 3:20]: Consultation Lifecycle & Prescription Controls

* **Visual**:
  - Authenticate as the assigned verified doctor.
  - Call `POST /api/v1/consultations/{id}/start` -> show status transitions to `IN_PROGRESS`.
  - Call `POST /api/v1/consultations/{id}/prescriptions` -> issue digital prescription with formulation, dosage, and dietary directions.
  - Call `POST /api/v1/consultations/{id}/complete` -> status transitions to `COMPLETED`.
  - Demonstrate ownership security: Query `GET /api/v1/consultations/{id}/prescriptions` with an unrelated patient's token -> show `403 Forbidden`.
  - Query with the owning patient's token -> show `200 OK` with complete prescription details.
* **Narrative**:
  > *"The clinical lifecycle enforces strict state progression: from SCHEDULED to IN_PROGRESS to COMPLETED. Only the assigned, verified doctor can issue prescriptions. Furthermore, our clinical authorization layer strictly enforces patient privacy: an unauthorized patient receives a 403 Forbidden when attempting to view another patient's medical records."*

---

### Segment 5 [3:20 – 4:15]: Concurrency, Race Condition Prevention & Automated Tests

* **Visual**:
  - In terminal, run: `pytest -v`.
  - Highlight `tests/concurrency/test_concurrency_race.py`.
  - Show all 14 tests passing green.
* **Narrative**:
  > *"To ensure zero double bookings, we enforce row-level locking via PostgreSQL SELECT ... FOR UPDATE coupled with a database-level unique constraint on slot_id. In our concurrency test suite, two threads simultaneously race to book the exact same slot. The test proves that exactly one request succeeds with 201 Created while the competing request receives a 409 Conflict, ensuring complete database integrity under extreme concurrency."*

---

### Segment 6 [4:15 – 5:00]: Observability, Operations & Submission Wrap-Up

* **Visual**:
  - Open `http://localhost:8000/health/ready` -> show `{"status": "ready", "database": "connected"}`.
  - Open `http://localhost:8000/metrics` -> show Prometheus request durations, total requests, and booking metrics.
  - Show `compose.yaml`, `.github/workflows/ci.yml`, and `docs/threat-model.md`.
* **Narrative**:
  > *"The backend includes full production observability: Prometheus metrics export latency histograms and request counters, while readiness probes ensure Kubernetes health checks pass. The repository is fully containerized with Docker Compose, automated via GitHub Actions CI, and backed by a 2-to-4 page architecture document, threat model, and disaster recovery plan. Thank you!"*
