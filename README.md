# Amrutam Telemedicine Backend

[![CI Pipeline](https://github.com/Shubhamgupta0309/amrutam-telemedicine-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/Shubhamgupta0309/amrutam-telemedicine-backend/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791.svg?logo=postgresql)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade, high-reliability telemedicine backend built for **Amrutam**. Designed as a domain-driven modular monolith to comfortably sustain **100,000 daily consultations** with sub-80ms p95 latencies, database-enforced double-booking prevention, distributed idempotency, clinical lifecycle controls, role-based access control (RBAC), and observability.

> 📹 **Demonstration Video**: A 5-minute complete architectural walkthrough and live API demonstration is included directly in the repository root: [**`demo-video.mp4`**](./demo-video.mp4).

---

## 📑 System Documentation & Architecture

| Component / Document | Path | Description |
|---|---|---|
| **Codebase & Infra** | [`app/`](./app), [`compose.yaml`](./compose.yaml), [`Dockerfile`](./Dockerfile) | Full application, background workers, and container definitions |
| **OpenAPI Schema** | [`openapi.json`](./openapi.json) | Exported OpenAPI 3.1 contract (23 versioned endpoints) |
| **Architecture Document** | [`docs/architecture.md`](./docs/architecture.md) | Deep-dive system architecture, domain boundaries, scaling strategies, and trade-offs |
| **Booking Sequence Diagram**| [`docs/booking-sequence.mmd`](./docs/booking-sequence.mmd) | Concurrency boundaries, locking, and duplicate handling |
| **Entity-Relationship Diagram**| [`docs/er-diagram.mmd`](./docs/er-diagram.mmd) | Database entities, foreign keys, and constraint rules |
| **Threat Model & Security** | [`docs/threat-model.md`](./docs/threat-model.md) | STRIDE analysis, attack surface, and healthcare data compliance |
| **Security Checklist** | [`docs/security-checklist.md`](./docs/security-checklist.md) | Pre-deployment verification across authentication, RBAC, and logs |
| **Disaster Recovery Plan** | [`docs/disaster-recovery.md`](./docs/disaster-recovery.md) | RPO (<5m), RTO (<30m), WAL archiving, and restoration steps |
| **Load Test Report** | [`docs/load-test-report.md`](./docs/load-test-report.md) | Traffic modeling for 100k daily consultations and p95 benchmarks |
| **Demo Walkthrough Video** | [`demo-video.mp4`](./demo-video.mp4) | 5-minute technical demonstration walkthrough |
| **CI/CD Pipeline** | [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) | Automated linting, PostgreSQL service test runs, and schema checks |

---

## 🛠️ Technology Stack

* **Backend Framework**: Python 3.11 + FastAPI + Pydantic v2
* **Database & ORM**: PostgreSQL 16 + SQLAlchemy 2.0 (with connection pooling)
* **Migrations**: Alembic
* **Security & Auth**: Argon2id / Bcrypt + PyJWT + RFC 6238 TOTP Multi-Factor Authentication
* **Idempotency & Concurrency**: Atomic row-level locks (`SELECT ... FOR UPDATE`), Unique slot constraints, and SHA-256 payload checksum matching
* **Asynchronous Jobs**: Transactional Outbox Pattern (`outbox_events` table) with exponential backoff worker
* **Observability**: Prometheus metrics (`/metrics`), structured JSON logging with Correlation IDs (`X-Correlation-ID`), and health checks (`/health/live`, `/health/ready`)
* **Infrastructure**: Docker, Docker Compose, GitHub Actions

---

## 🚀 Quickstart Guide

### Option 1: Running via Docker Compose (Recommended for Production Stack)

Ensure Docker and Docker Compose are installed, then run:

```bash
# 1. Clone repository
git clone https://github.com/Shubhamgupta0309/amrutam-telemedicine-backend.git
cd amrutam-telemedicine-backend

# 2. Copy environment configuration
cp .env.example .env

# 3. Spin up full stack (FastAPI, PostgreSQL, Redis, Outbox Worker, Prometheus)
docker compose up --build -d
```

Once running:
* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
* **Health Probes**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)
* **Prometheus Dashboard**: [http://localhost:9090](http://localhost:9090)

---

### Option 2: Local Development Setup

```bash
# 1. Create and activate Python virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure local environment
cp .env.example .env

# 4. Run database migrations
alembic upgrade head

# 5. Start development server
uvicorn app.main:app --reload --port 8000
```

---

## 🧪 Running Automated Tests

The test suite covers unit, integration, concurrency race conditions, and security boundaries.

```bash
# Run complete test suite with verbose output
pytest -v

# Run concurrency race condition test specifically
pytest tests/concurrency/test_concurrency_race.py -v

# Run with test execution durations
pytest -v --durations=10
```

### Test Coverage Highlights
* **Double Booking Prevention**: Concurrent thread execution tests proving two simultaneous booking requests for the same slot result in exactly one `201 Created` and one `409 Conflict`.
* **Idempotency Guarantees**: Proves identical `Idempotency-Key` replays original response; modified payload triggers `409 Conflict`.
* **Clinical Ownership**: Asserts that Patient B receives `403 Forbidden` when attempting to access Patient A's prescription.
* **Webhook Replay Protection**: Proves duplicate provider event IDs are handled idempotently.
* **Zero Secret Leakage**: Asserts audit logs and structured stdout logs never contain passwords or raw authorization headers.

---

## 🔒 Security & Concurrency Guarantees

### 1. Atomic Double-Booking Elimination
```sql
-- Atomic lock acquired in transaction
SELECT * FROM availability_slots WHERE id = :slot_id FOR UPDATE;
-- Followed by atomic status transition and relational 1:1 constraint
INSERT INTO consultations (patient_id, doctor_id, slot_id, status) ...;
```
If a slot is not in `AVAILABLE` state, the transaction rolls back immediately with a `409 Conflict: SLOT_ALREADY_RESERVED`.

### 2. Distributed Idempotency Key Handling
* Client supplies header: `Idempotency-Key: <unique-uuid>`.
* The server computes `SHA-256(user_id + request_body)`.
* **Replay**: Matching key + matching hash \(\to\) returns original cached response code and body.
* **Tampering**: Matching key + mismatched payload \(\to\) rejects with `409 Conflict: IDEMPOTENCY_PAYLOAD_MISMATCH`.

### 3. Transactional Outbox Pattern
Booking reservations, idempotency records, and notification events are committed in the **exact same database transaction**. The background worker (`app.workers.outbox_worker`) processes notifications asynchronously, guaranteeing at-least-once delivery without risking failed booking transactions.

---

## 🌐 API Endpoint Specification

All endpoints are versioned under `/api/v1`:

| Method | Path | Role Required | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Public | Register patient or doctor |
| `POST` | `/api/v1/auth/login` | Public | Login with credentials, returns JWT tokens or MFA challenge |
| `POST` | `/api/v1/auth/mfa/setup` | Authenticated | Generate TOTP secret and QR code URI |
| `POST` | `/api/v1/auth/mfa/verify` | Authenticated | Verify 6-digit TOTP code to complete login / enable MFA |
| `POST` | `/api/v1/auth/refresh` | Public | Refresh expired access token using valid refresh token |
| `GET` | `/api/v1/users/me` | Authenticated | Retrieve current user profile and role details |
| `PUT` | `/api/v1/users/me` | Authenticated | Update current user's profile information |
| `GET` | `/api/v1/doctors` | Public | Search and filter verified doctors by specialty with pagination |
| `GET` | `/api/v1/doctors/{id}` | Public | Retrieve doctor profile and consultation fees |
| `GET` | `/api/v1/doctors/{id}/availability` | Public | View available appointment slots for a doctor |
| `POST` | `/api/v1/doctors/{id}/availability` | Doctor (Owner) | Schedule new availability slot (`end_at > start_at`) |
| `POST` | `/api/v1/doctors/{id}/verify` | Admin | Verify doctor registration and credentials |
| `POST` | `/api/v1/bookings` | Patient | Book slot atomically (requires `Idempotency-Key`) |
| `GET` | `/api/v1/bookings` | Authenticated | List user's bookings with role-based ownership filtering |
| `GET` | `/api/v1/bookings/{id}` | Authenticated | Get booking details with ownership verification |
| `POST` | `/api/v1/bookings/{id}/cancel` | Authenticated | Cancel booking and release slot back to `AVAILABLE` |
| `POST` | `/api/v1/consultations/{id}/start` | Doctor (Owner) | Transition consultation: `SCHEDULED` \(\to\) `IN_PROGRESS` |
| `POST` | `/api/v1/consultations/{id}/complete` | Doctor (Owner) | Transition consultation: `IN_PROGRESS` \(\to\) `COMPLETED` |
| `POST` | `/api/v1/consultations/{id}/prescriptions` | Doctor (Verified)| Issue digital prescription with medications & advice |
| `GET` | `/api/v1/consultations/{id}/prescriptions` | Patient / Doctor| Retrieve prescriptions with strict ownership check |
| `POST` | `/api/v1/payments/create-intent` | Patient | Initialize payment intent for consultation |
| `POST` | `/api/v1/payments/webhook` | Provider | Ingest webhook events with HMAC SHA-256 signature check |
| `GET` | `/api/v1/admin/analytics` | Admin | View operational consultation counts and revenues |
| `GET` | `/health/live` | Public | Liveness probe (returns 200 if process alive) |
| `GET` | `/health/ready` | Public | Readiness probe (verifies database connectivity) |
| `GET` | `/metrics` | Public | Prometheus scrape target for latency and traffic metrics |

---

## 👤 Author
* **Shubham Gupta** ([@Shubhamgupta0309](https://github.com/Shubhamgupta0309))
* Repository: [https://github.com/Shubhamgupta0309/amrutam-telemedicine-backend.git](https://github.com/Shubhamgupta0309/amrutam-telemedicine-backend.git)
