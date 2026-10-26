# Disaster Recovery & Business Continuity Plan

This plan establishes the backup frequency, retention policies, failover mechanisms, and step-by-step restoration procedures for the **Amrutam Telemedicine Backend**.

---

## 1. Recovery Objectives

| Metric | Target | Description |
|---|---|---|
| **RPO (Recovery Point Objective)** | **< 5 minutes** | Maximum acceptable data loss period in the event of an catastrophic failure. Achieved via continuous Write-Ahead Log (WAL) archiving. |
| **RTO (Recovery Time Objective)** | **< 30 minutes** | Maximum acceptable downtime to restore system operations in a secondary region or fresh cluster. |
| **Availability SLA** | **99.95%** | Permitted unplanned downtime is less than 21.9 minutes per month. |

---

## 2. Backup Strategy & Retention Policies

### 2.1 Database Backups (PostgreSQL)
1. **Continuous WAL Archiving**:
   - PostgreSQL WAL files are continuously streamed to an encrypted, immutable cloud object store (e.g. AWS S3 with Object Lock / Glacier).
   - Enables Point-In-Time Recovery (PITR) to any second within the retention window.
2. **Automated Daily Snapshots**:
   - Automated full logical and physical database snapshots executed daily at `02:00 UTC` during off-peak traffic.
   - Tooling: `pg_dump` for logical portability; `pgBackRest` / `WAL-G` for high-throughput physical block-level backup.
3. **Retention Schedule**:
   - Daily snapshots: Retained for 30 days.
   - Weekly snapshots: Retained for 12 weeks.
   - Monthly compliance archives: Retained for 7 years (mandated by medical record retention rules).

### 2.2 Backup Storage & Encryption
- All backup artifacts are encrypted using AES-256 (KMS-managed keys).
- Backups are replicated to a geographically distinct secondary region (e.g., primary in AWS `ap-south-1` Mumbai, secondary in `ap-southeast-1` Singapore).

---

## 3. High Availability & Failover Architecture

```
[ Route 53 / Cloudflare DNS Health Check ]
                 │
        ┌────────┴────────┐
        ▼                 ▼ (Standby)
┌───────────────┐ ┌───────────────┐
│ Primary Region│ │ Standby Region│
│  (ap-south-1) │ │(ap-southeast-1│
├───────────────┤ ├───────────────┤
│ FastAPI Nodes │ │ FastAPI Nodes │
│      │        │      │          │
│      ▼        │      ▼          │
│ PostgreSQL    │───► PostgreSQL │
│ Primary (R/W) │ │ Standby (R/O) │
└───────────────┘ └───────────────┘
```

- **Database Multi-AZ Deployment**:
  - PostgreSQL configured with synchronous replication across multiple availability zones within the primary region.
  - Asynchronous streaming replication to the disaster recovery secondary region.
- **Stateless Application Layer**:
  - FastAPI container instances run across multiple zones behind an Application Load Balancer with auto-scaling (minimum 3 instances).

---

## 4. Step-by-Step Disaster Restoration Procedure

### Scenario A: Accidental Data Corruption (Point-in-Time Recovery)
If a software bug or operator error corrupts data at `2026-10-26 14:15:00 UTC`:

1. **Stop Application Traffic**:
   ```bash
   # Temporarily place application in maintenance mode
   docker compose stop backend worker
   ```

2. **Restore Base Snapshot**:
   Identify the latest consistent snapshot taken before the incident:
   ```bash
   pgbackrest --stanza=amrutam --type=time "--target=2026-10-26 14:14:50 UTC" restore
   ```

3. **Replay WAL to Target Timestamp**:
   Configure `postgresql.conf` / `recovery.signal`:
   ```ini
   restore_command = 'pgbackrest --stanza=amrutam archive-get %f "%p"'
   recovery_target_time = '2026-10-26 14:14:50 UTC'
   recovery_target_action = 'promote'
   ```

4. **Verify Database Integrity & Reconnect**:
   Start PostgreSQL, verify records, run schema validation, and restart API containers.

---

### Scenario B: Total Region Outage (Secondary Region Promotion)

1. **DNS Cutover**:
   Update Route 53 failover routing policy to point `api.amrutam.co.in` to the secondary region load balancer.

2. **Promote Standby Database**:
   ```sql
   -- On Standby PostgreSQL replica
   SELECT pg_promote();
   ```

3. **Verify Replica Promotion**:
   ```sql
   SELECT pg_is_in_recovery(); -- Must return FALSE
   ```

4. **Start Application Cluster**:
   Bring up API and worker containers in the secondary region pointing to the newly promoted primary database.

5. **Run Synthetic Health Checks**:
   ```bash
   curl -f https://api.amrutam.co.in/health/ready
   ```

---

## 5. Testing & Drill Cadence

- **Quarterly Tabletop & Dry-Run Simulations**: Simulated region failure conducted every quarter on staging environments.
- **Automated Restore Verification**: A dedicated CI workflow restores the latest daily backup snapshot to a scratch database container every week, validating checksums and running the test suite against restored data.
