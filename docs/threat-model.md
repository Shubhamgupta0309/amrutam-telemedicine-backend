# Threat Model & Security Architecture

This document outlines the threat landscape, trust boundaries, attack surface analysis, and OWASP Top 10 mitigations for the **Amrutam Telemedicine Backend**.

---

## 1. System Assets & Data Classification

| Asset Category | Data Elements | Classification | Impact of Compromise |
|---|---|---|---|
| **Protected Health Information (PHI)** | Diagnoses, medications, consultation clinical notes, symptoms | **Restricted / PHI** | High: Severe privacy violation, regulatory non-compliance (DISHA / Telemedicine Practice Guidelines India). |
| **Personally Identifiable Information (PII)** | Patient names, phone numbers, email addresses | **Confidential** | Moderate to High: Identity theft, phishing risks. |
| **Doctor Credentials** | Medical council registration numbers, state verification documents | **Confidential** | High: Risk of impersonation and quackery. |
| **Authentication & Secrets** | Argon2 password hashes, JWT signing keys, MFA TOTP secrets, Webhook HMAC keys | **Restricted** | Critical: Total system compromise, unauthorized elevation of privilege. |
| **Transactional Data** | Booking states, payment provider event logs, audit trails | **Internal** | Moderate: Financial discrepancies, dispute resolution hurdles. |

---

## 2. Trust Boundaries & Attack Surface Analysis

```
[ Public Internet ]
       │
       ▼ (HTTPS / TLS 1.3)
┌─────────────────────────────────────────────────────────────┐
│ Trust Boundary 1: Edge & Ingress                          │
│ - Rate Limiting (60 req/min/IP)                             │
│ - Correlation ID Injection (X-Correlation-ID)              │
│ - Strict Request Size Limits & Validation                   │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Trust Boundary 2: Application Layer (FastAPI)              │
│ - JWT Bearer Authentication & Cryptographic Verification   │
│ - Role-Based Access Control (Patient, Doctor, Admin)        │
│ - Resource Ownership Validation (Strict Multi-Tenancy)     │
│ - Idempotency Key Validation & SHA-256 Payload Matching     │
└─────────────────────────────────────────────────────────────┘
       │
       ├──────────────────────────────┐
       ▼ (Internal Network / TLS)      ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ Trust Boundary 3: Database    │ │ Trust Boundary 4: Asynchronous│
│ (PostgreSQL & Redis)         │ │ Outbox Event Workers         │
│ - Row-Level Locking          │ │ - Isolated worker execution  │
│ - Foreign Key Constraints    │ │ - Exponential backoff retry  │
│ - Append-only Audit Logs     │ │ - Zero patient secret payload│
└──────────────────────────────┘ └──────────────────────────────┘
```

---

## 3. STRIDE Threat Analysis & Mitigations

| Threat Category | Potential Attack Vector | Applied Mitigation in Amrutam Backend |
|---|---|---|
| **Spoofing** | Forged JWT access tokens, fake payment webhooks | Strict HMAC-SHA256 signature verification for webhooks with secret keys; asymmetric/symmetric JWT validation with expiration verification and role claims. |
| **Tampering** | Modifying prescription records or intercepting requests in transit | Prescriptions are immutable once issued; TLS 1.3 enforced; Pydantic validation guarantees schema compliance. |
| **Repudiation** | Doctor denies issuing a prescription; patient denies cancelling a booking | Append-only `audit_logs` table records actor ID, action type, client IP, timestamp, and correlation ID for every state mutation. |
| **Information Disclosure** | Leakage of medical notes or passwords in logs, insecure direct object reference (IDOR) | JSON log formatter with proactive sensitive field redaction (passwords, tokens, cards redacted); strict object ownership checks in booking and prescription endpoints. |
| **Denial of Service** | Flooding booking endpoints, exhaust database connection pool | In-memory / Redis token-bucket rate limiting (429 Too Many Requests); bounded connection pooling (SQLAlchemy `pool_size=20, max_overflow=10`). |
| **Elevation of Privilege** | Normal patient or doctor accessing admin analytics or verifying doctors | Server-side role dependency (`require_roles("admin")`) checks decoded JWT claims against the persistent user role. |

---

## 4. OWASP Top 10 (2021) Mitigations

1. **A01: Broken Access Control**:
   - Every sensitive resource (bookings, prescriptions) validates user ownership in the service layer (`booking.patient_id == user.id` or `booking.doctor_id == doctor.id`).
   - Admin routes explicitly enforce `role == "admin"`.
2. **A02: Cryptographic Failures**:
   - Passwords hashed using Argon2id / Bcrypt (`pwd_context = CryptContext(schemes=["argon2", "bcrypt"])`).
   - TOTP MFA keys generated using cryptographically strong random seeds (`pyotp.random_base32()`).
3. **A03: Injection**:
   - Zero raw SQL string concatenation; parameterized queries via SQLAlchemy 2.0 ORM.
   - Pydantic models sanitize and validate all request data.
4. **A04: Insecure Design**:
   - Atomic concurrency locking (`SELECT FOR UPDATE`) prevents double booking.
   - Idempotency records prevent duplicate reservation and billing operations.
5. **A05: Security Misconfiguration**:
   - CORS origins configured via environment variables.
   - Verbose debugging disabled by default in production (`DEBUG=false`).
6. **A06: Vulnerable and Outdated Components**:
   - Pinned dependencies in `requirements.txt` and automated dependency scanning in GitHub Actions.
7. **A07: Identification and Authentication Failures**:
   - Short-lived JWT access tokens (60 minutes) and distinct refresh tokens (7 days).
   - MFA challenge step for privileged doctor and admin workflows.
8. **A08: Software and Data Integrity Failures**:
   - Webhooks validated with HMAC SHA256 signatures before parsing body.
   - Database migrations tracked deterministically through Alembic.
9. **A09: Security Logging and Monitoring Failures**:
   - Correlation IDs injected into request context and logged across all service calls.
   - Prometheus metrics monitor anomalous error rates and high-frequency latencies.
10. **A10: Server-Side Request Forgery (SSRF)**:
    - Outbox event workers execute only predefined event handlers without accepting user-supplied target callback URLs.

---

## 5. Indian Healthcare Compliance Considerations

The backend architecture is structured to support key tenets of Indian healthcare data standards:
* **Telemedicine Practice Guidelines (2020, Medical Council of India / MoHFW)**:
  - Doctor identity verification required prior to issuing digital prescriptions (`verification_status == "VERIFIED"`).
  - Prescriptions strictly record date, diagnosis, medication formulation, dosage, and dietary advice.
* **Digital Information Security in Healthcare Act (DISHA Draft)**:
  - Explicit consent and ownership boundaries: patients own their consultation history and cannot view records of other patients.
  - Audit trail retains non-repudiable logs of access to clinical summaries.
* **Information Technology Act (Section 43A) & SPDI Rules**:
  - Sensitive Personal Data or Information (SPDI) is protected by reasonable security practices including encryption and role-based access.
