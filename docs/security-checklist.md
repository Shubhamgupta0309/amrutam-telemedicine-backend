# Security Verification Checklist

This checklist provides a pre-flight security evaluation for deploying the **Amrutam Telemedicine Backend** to staging and production environments.

---

## 1. Authentication & Session Security

- [x] **Secure Password Hashing**: Passwords hashed using Argon2id / Bcrypt (`app/core/security.py`).
- [x] **Short-Lived JWT Access Tokens**: Expiration configured to 60 minutes via `ACCESS_TOKEN_EXPIRE_MINUTES`.
- [x] **Distinct Refresh Tokens**: Refresh tokens marked with `type: refresh` and kept isolated from access tokens.
- [x] **Multi-Factor Authentication (MFA)**: TOTP MFA workflow implemented with RFC 6238 compliant base32 secrets and time-drift validation.
- [x] **Timing Attack Resilience**: Password verification and HMAC comparison utilize constant-time comparison (`hmac.compare_digest`).

---

## 2. Authorization & RBAC

- [x] **Server-Side Enforcement**: All access control rules validated in FastAPI dependency injectors, independent of client UI state.
- [x] **Role Separation**: `patient`, `doctor`, and `admin` roles explicitly defined and enforced via `require_roles()`.
- [x] **Resource Ownership (Anti-IDOR)**:
  - Patients can only query and cancel their own consultations (`Consultation.patient_id == user.id`).
  - Doctors can only view and complete consultations assigned to them (`Consultation.doctor_id == doctor.id`).
  - Prescriptions strictly inaccessible to non-participating patients.
- [x] **Medical Credential Gating**: Only doctors verified by an administrator (`verification_status == "VERIFIED"`) can publish availability slots and issue prescriptions.

---

## 3. Data Integrity & Concurrency Control

- [x] **Atomic Double-Booking Protection**: Slot reservations executed within an atomic database transaction using `SELECT ... FOR UPDATE` row locks.
- [x] **Idempotency Keys**:
  - `Idempotency-Key` header enforced on critical state-mutating booking requests.
  - Repeated identical requests replay original cached responses without duplicate side effects.
  - Reusing the same idempotency key with modified payloads triggers an immediate `409 Conflict`.
- [x] **Unique Constraints**:
  - Normalized unique email address.
  - Unique doctor registration number.
  - Unique `slot_id` on consultations to prevent multi-booking at the relational schema level.
  - Unique `provider_reference` on payments to eliminate duplicate webhook processing.

---

## 4. Encryption & Secret Management

- [x] **Secrets via Environment Variables**: Zero hardcoded production secrets in source control.
- [x] **Sensitive Log Redaction**: Custom `JSONFormatter` redacts passwords, tokens, API keys, card numbers, and authorization headers from stdout.
- [x] **Audit Log Sanitization**: Audit log entries redact credentials and sensitive health fields before persisting to the database.
- [x] **TLS Ready**: Docker container configured to run behind reverse proxies (Nginx / Cloudflare / AWS ALB) terminating TLS 1.3.

---

## 5. Input Validation & API Defense

- [x] **Pydantic V2 Validation**: All request bodies, path parameters, and query strings strongly typed with bounds checking.
- [x] **Rate Limiting**: Sliding window rate limiting middleware enforces a maximum threshold of 60 requests per minute per IP.
- [x] **Bounded Request Payloads**: Pydantic models impose length constraints on free-text inputs (e.g. notes max 1000 characters).
- [x] **Payment Webhook Signature Validation**: Webhooks verified via HMAC SHA-256 before request body deserialization.

---

## 6. Observability & Auditing

- [x] **Request Correlation**: Correlation ID extracted from `X-Correlation-ID` / `X-Request-ID` or generated, and propagated across logs and response headers.
- [x] **Append-Only Audit Trail**: Every sensitive action (`USER_REGISTER`, `LOGIN_SUCCESS`, `SLOT_CREATED`, `BOOKING_CREATED`, `CONSULTATION_STARTED`, `PRESCRIPTION_ISSUED`, `PAYMENT_WEBHOOK_PROCESSED`) recorded in `audit_logs`.
- [x] **Prometheus Instrumentation**: Request counters, latency histograms, and booking counters exposed via `/metrics`.
- [x] **Health Probes**: Liveness (`/health/live`) and database readiness (`/health/ready`) probes operational.
