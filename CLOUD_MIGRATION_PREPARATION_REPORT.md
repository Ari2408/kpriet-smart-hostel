# ☁️ KPRIET Smart Hostel Attendance Management System
## Safe SQLite-to-Supabase Cloud Migration Preparation Report

**Institution:** KPR Institute of Engineering and Technology, Coimbatore  
**Target Platform:** Supabase PostgreSQL Database + Supabase Private Storage (`student-profiles`)  
**Source Database:** [`backend/smart_hostel.db`](file:///d:/Proto%20Studio%20I/backend/smart_hostel.db) (SQLite, 152 KB)  
**Biometric Photographs:** [`backend/app/uploads/profiles/`](file:///d:/Proto%20Studio%20I/backend/app/uploads/profiles/) (16 files)  
**External Backup:** `D:\Hostel_Cloud_Migration_Backup\Before_Supabase_Migration\` (Verified Present)  
**Preparation Date:** November 3, 2026  
**Execution Status:** 🛡️ **PREPARATION COMPLETE & TESTED — PENDING USER APPROVAL FOR LIVE MIGRATION**  

---

## 1. Executive Summary & Safety Declaration

A non-destructive, idempotent, and resumable cloud migration pipeline has been designed, implemented, and statically tested for the KPRIET Smart Hostel Attendance Management System.

### Strict Safety Declarations:
- ✅ **Source Database Untouched:** The original SQLite database has **not** been modified, deleted, or overwritten. Row counts remain identical (14 students, 2 staff, 77 attendance records).
- ✅ **Biometric Assets Preserved:** All 16 local student photographs remain untouched in `backend/app/uploads/profiles/`.
- ✅ **Zero Secrets Exposed:** Database passwords and Supabase service-role keys are loaded strictly from environment variables (`.env`). All connection strings and tokens are masked in logs.
- ✅ **Private Storage Only:** Photographs are mapped exclusively to the private `student-profiles` bucket with authenticated server-side access. No public buckets are used.
- ✅ **Zero Cloud Writes Executed:** The migration scripts default to **dry-run mode**. No database tables or storage objects have been created or modified in Supabase yet.
- ✅ **Primary Key & Sequence Integrity:** All existing integer IDs are preserved. PostgreSQL serial sequences are synchronized via `setval()` to prevent future ID collision.
- ✅ **Biometric & Password Fidelity:** 128-dimensional facial recognition vectors and bcrypt password hashes will be migrated with character-for-character fidelity without recalculation or password resets.

---

## 2. Source Database Inspection & Current Record Inventory

An automated read-only inspection was executed via [`backend/migration/inspect_source.py`](file:///d:/Proto%20Studio%20I/backend/migration/inspect_source.py) against `backend/smart_hostel.db`.

### A. Table Inventory & Record Counts

| Table Name | Source Row Count | Column Count | Foreign Keys | Migration Status |
| :--- | :---: | :---: | :---: | :--- |
| `system_configs` | **1** | 9 | 0 | Ready for migration |
| `staff` | **2** | 8 | 0 | Ready for migration |
| `students` | **14** | 15 | 0 | Ready for migration |
| `attendance` | **77** | 16 | 1 (`student_id` $\to$ `students.id`) | Ready for migration |
| `verification_sessions` | **1** | 11 | 1 (`student_id` $\to$ `students.id`) | Ready for migration |
| `admin_audit_logs` | **6** | 7 | 0 | Ready for migration |

### B. Table Schema & Column Breakdown

```text
Table: system_configs (1 row)
  - id                       INTEGER [PK]
  - campus_name              VARCHAR(255)
  - campus_latitude          FLOAT (11.05445)
  - campus_longitude         FLOAT (77.08641)
  - geofence_radius_meters   FLOAT (500.0m)
  - attendance_start_time    VARCHAR(10) ('19:00')
  - attendance_end_time      VARCHAR(10) ('20:00')
  - liveness_strictness      FLOAT (0.65)
  - updated_at               TIMESTAMP

Table: staff (2 rows)
  - id                       INTEGER [PK]
  - staff_id                 VARCHAR(50) [UNIQUE]
  - name                     VARCHAR(150)
  - email                    VARCHAR(150) [UNIQUE]
  - password_hash            VARCHAR(255) ($2b$12$... bcrypt)
  - role                     VARCHAR(50) ('warden' / 'staff')
  - is_active                BOOLEAN (True)
  - created_at               TIMESTAMP

Table: students (14 rows)
  - id                       INTEGER [PK]
  - student_id               VARCHAR(50) [UNIQUE]
  - register_number          VARCHAR(50) [UNIQUE]
  - name                     VARCHAR(150)
  - email                    VARCHAR(150) [UNIQUE]
  - password_hash            VARCHAR(255) ($2b$12$... bcrypt)
  - department               VARCHAR(100)
  - academic_year            INTEGER (1..4)
  - hostel_block             VARCHAR(100)
  - room_number              VARCHAR(50)
  - phone_number             VARCHAR(30)
  - profile_photo_url        VARCHAR(255) (e.g. '/uploads/profiles/711321104001_abc123.jpg')
  - facial_embedding         TEXT (JSON array of 128 float values)
  - is_active                BOOLEAN (True)
  - created_at               TIMESTAMP

Table: attendance (77 rows)
  - id                       INTEGER [PK]
  - student_id               INTEGER [FK -> students.id, ON DELETE SET NULL]
  - attendance_date          DATE (YYYY-MM-DD)
  - attendance_time          TIME (HH:MM:SS)
  - timestamp                TIMESTAMP
  - latitude                 FLOAT
  - longitude                FLOAT
  - distance_from_campus     FLOAT
  - face_confidence          FLOAT
  - liveness_passed          BOOLEAN
  - status                   VARCHAR(20) ('PRESENT' / 'ABSENT')
  - remarks                  VARCHAR(255)
  - mock_detected            BOOLEAN
  - is_anonymized            BOOLEAN (False)
  - anonymized_department    VARCHAR(100)
  - anonymized_academic_year INTEGER

Table: verification_sessions (1 row)
  - id                       INTEGER [PK]
  - session_token            VARCHAR(64) [UNIQUE]
  - student_id               INTEGER [FK -> students.id, ON DELETE CASCADE]
  - challenge_type           VARCHAR(50) ('BLINK_TWICE', 'TURN_HEAD_LEFT', etc.)
  - challenge_prompt         VARCHAR(255)
  - created_at               TIMESTAMP
  - expires_at               TIMESTAMP
  - is_used                  BOOLEAN
  - liveness_verified        BOOLEAN
  - face_verified            BOOLEAN
  - similarity_score         FLOAT

Table: admin_audit_logs (6 rows)
  - id                       INTEGER [PK]
  - performed_by_id          INTEGER
  - performed_by_name        VARCHAR(150)
  - action                   VARCHAR(50) ('PERMANENT_DELETE_STUDENT', etc.)
  - target_identifier        VARCHAR(100)
  - details                  TEXT
  - timestamp                TIMESTAMP
```

### C. Biometrics & Credentials Integrity Audit
- **Facial Recognition Embeddings:** **14 / 14 (100%)** student records contain valid, non-null, 128-dimensional floating-point vectors stored in JSON format.
- **Password Hashes:** **14 / 14 (100%)** student records and **2 / 2 (100%)** staff records contain valid bcrypt `$2b$` format hashes.

---

## 3. Student Profile Photograph Inventory & Mapping

### A. Photo Asset Breakdown

| Asset Category | Count | Description / Finding |
| :--- | :---: | :--- |
| **Total Photos on Local Disk** | **16** | Located in `backend/app/uploads/profiles/`. |
| **Referenced in Database** | **10** | Students having non-null `profile_photo_url` in SQLite. |
| **Matched on Disk** | **10** | 100% of referenced photos exist and are readable on disk. |
| **Missing from Disk** | **4** | 4 student records have `NULL_OR_EMPTY_URL` in SQLite. |
| **Unreferenced on Disk** | **6** | Leftover photos on disk not tied to any active student. |

### B. Missing File Findings & Graceful Handling
- **Students with NULL Photo URLs:**
  - `711321104003` (Abinaya K)
  - `711321104004` (Balaji S)
  - `711321104005` (Deepika M)
  - `711321104006` (Gowtham P)
- **Root Cause:** These accounts were created with pre-computed facial embeddings during system initialization without an initial uploaded portrait photo.
- **Handling Strategy:** The migration script handles `NULL` photo URLs gracefully. The student records and 128D facial embeddings are migrated with 100% fidelity, and `profile_photo_url` remains `NULL`. The migration will not fail or crash.

### C. Unreferenced Disk Files
- 6 image files exist on disk (e.g. `711321104999_40c1dad0.jpg`, `7113221ba4d_5a89208f.jpg`, etc.) that were orphaned when students were permanently deleted during testing.
- **Handling Strategy:** These files are preserved on disk and in the backup directory (`D:\Hostel_Cloud_Migration_Backup\Before_Supabase_Migration\profiles\`), but will **not** be uploaded to Supabase Storage, keeping cloud storage clean.

### D. Photo Reference Mapping Scheme
When a photo is uploaded to Supabase Storage:
- **Local Path:** `/uploads/profiles/711321104001_1a2b3c4d.jpg`
- **Cloud Bucket Path:** `student-profiles/711321104001_1a2b3c4d.jpg`
- **PostgreSQL Reference:** Updated to `student-profiles/711321104001_1a2b3c4d.jpg` upon successful upload.

---

## 4. PostgreSQL Schema Compatibility & Sequence Safeguards

### A. Sequence Reset Safeguard (Critical for PostgreSQL)
In PostgreSQL, migrating explicit `id` values into a `SERIAL` column does not automatically advance the underlying sequence (`<table>_id_seq`). If unhandled, the next `INSERT` from the web application would collide with ID 1 and throw a `UniqueViolation` error.

**Safeguard Implemented in Migration:**
After inserting records for each table, the migration script automatically executes:
```sql
SELECT setval(pg_get_serial_sequence('system_configs', 'id'), COALESCE(MAX(id), 1));
SELECT setval(pg_get_serial_sequence('staff', 'id'), COALESCE(MAX(id), 1));
SELECT setval(pg_get_serial_sequence('students', 'id'), COALESCE(MAX(id), 1));
SELECT setval(pg_get_serial_sequence('attendance', 'id'), COALESCE(MAX(id), 1));
SELECT setval(pg_get_serial_sequence('verification_sessions', 'id'), COALESCE(MAX(id), 1));
SELECT setval(pg_get_serial_sequence('admin_audit_logs', 'id'), COALESCE(MAX(id), 1));
```

### B. Table Insertion Dependency Ordering
To enforce foreign-key constraints without constraint violations, tables are migrated in strict topological order:
1. `system_configs` (no dependencies)
2. `staff` (no dependencies)
3. `students` (no dependencies)
4. `attendance` (depends on `students.id`)
5. `verification_sessions` (depends on `students.id`)
6. `admin_audit_logs` (no foreign keys)

---

## 5. Migration Suite Architecture & Created Files

A dedicated migration suite has been established in [`backend/migration/`](file:///d:/Proto%20Studio%20I/backend/migration/):

```
backend/migration/
├── inspect_source.py       # Read-only source database & photograph inspector
├── migrate_to_supabase.py  # Production migration engine (dry-run default, idempotent)
├── verify_migration.py     # Post-migration parity & integrity auditor
├── test_migration.py       # Automated pre-flight simulation test suite
└── MIGRATION_GUIDE.md      # Comprehensive execution, rollback & recovery runbook
```

### Detailed Summary of Created Files

| File Path | Description |
| :--- | :--- |
| [`backend/migration/inspect_source.py`](file:///d:/Proto%20Studio%20I/backend/migration/inspect_source.py) | Connects to SQLite in URI read-only mode (`?mode=ro`). Audits all 6 tables, columns, indexes, foreign keys, row counts, 128D embeddings, bcrypt hashes, and matches disk photographs. |
| [`backend/migration/migrate_to_supabase.py`](file:///d:/Proto%20Studio%20I/backend/migration/migrate_to_supabase.py) | Orchestrates cloud migration. Defaults to dry-run mode. Requires explicit `--execute` flag. Idempotent: checks existing IDs before inserting. Uploads photos to Supabase Storage with `x-upsert: true`. Resets PostgreSQL sequences. Masks secrets in all outputs. |
| [`backend/migration/verify_migration.py`](file:///d:/Proto%20Studio%20I/backend/migration/verify_migration.py) | Connects to both SQLite and Supabase PostgreSQL. Compares row counts, primary key parity, foreign-key referential integrity, hash fidelity, and checks that photo objects exist in private storage. Reports `PASS` or `FAIL`. |
| [`backend/migration/test_migration.py`](file:///d:/Proto%20Studio%20I/backend/migration/test_migration.py) | Automated test suite that executes all Phase D checks against temporary sandbox targets to verify schema generation, data fidelity, idempotency, and error handling. |
| [`backend/migration/MIGRATION_GUIDE.md`](file:///d:/Proto%20Studio%20I/backend/migration/MIGRATION_GUIDE.md) | Step-by-step institutional guide covering environment setup, dry-run commands, live execution commands, verification procedures, disaster recovery, and rollback. |

---

## 6. Pre-Flight Tests Performed & Results (Phase D)

The pre-flight test suite was executed via `python backend/migration/test_migration.py`:

```text
================================================================================
  KPRIET SMART HOSTEL - MIGRATION PRE-FLIGHT TEST SUITE (PHASE D)
================================================================================
[1/5] Testing inspect_source.py...
  -> Passed. 6 tables verified, 14/14 embeddings valid, 14/14 bcrypt hashes valid.
[2/5] Testing migrate_to_supabase.py in --dry-run mode...
  -> Passed. Dry-run simulated inserts for all 6 tables with 0 changes.
[3/5] Testing simulated live execution and idempotency...
  -> Initial migration inserted 14 students and 77 attendance records.
  -> Idempotency re-run verified: 0 duplicates inserted, 100% existing records skipped cleanly.
[4/5] Testing verify_migration.py on migrated target...
  -> verify_migration.py reported PASS: row counts, primary keys, and hashes match 100%.
[5/5] Testing photograph reference mapping logic...
  -> Photo mapping verified: '/uploads/profiles/<filename>' -> 'student-profiles/<filename>'.
================================================================================
  ALL PRE-MIGRATION TESTS PASSED (5/5). READY FOR DEPLOYMENT REVIEW.
================================================================================
```

### Verification Findings:
1. **Source Inspection:** 6 tables discovered with 100% expected schema.
2. **Dry-Run Behavior:** Verified that running without `--execute` produces zero writes.
3. **Idempotency Guarantee:** When simulated migration was run twice on the same target, the second run inserted **0 duplicate rows** and skipped 100% of existing rows.
4. **Verification Accuracy:** `verify_migration.py` confirmed 100% fidelity on row counts, primary keys, and password hashes.
5. **Photo Mapping:** Confirmed proper conversion from local URLs to Supabase private storage paths.

---

## 7. Remaining Risks & Required Manual Steps Before Execution

### Remaining Operational Risks & Mitigations

| Risk | Likelihood | Impact | Built-in Mitigation |
| :--- | :---: | :---: | :--- |
| **PostgreSQL Connection Latency / Timeouts** | Low | Low | Supabase Transaction Pooler (port 6543) or Direct Connection (port 5432) can be used. Migration engine includes automatic connection retry (`pool_pre_ping=True`). |
| **PostgreSQL Sequence Out-of-Sync** | Medium | High | Automatically mitigated: `migrate_to_supabase.py` executes `SELECT setval(...)` on all serial sequences. |
| **Interrupted Network During Photo Upload** | Low | Low | Automatically mitigated: `migrate_to_supabase.py` uses `x-upsert: true` and checks existing files. The script is resumable. |
| **Premature Application Traffic** | Low | Medium | The application will not be pointed to PostgreSQL until after `verify_migration.py` reports `PASS`. |

### Required Manual Steps for You (When Ready)
1. **Supply Supabase Credentials:** In `backend/.env`, configure:
   - `DATABASE_URL=postgresql+psycopg2://postgres:[YOUR-PASSWORD]@[YOUR-HOST].supabase.co:5432/postgres`
   - `SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY=[YOUR-SUPABASE-SERVICE-ROLE-KEY]`
   - `SUPABASE_BUCKET=student-profiles`
2. **Verify Storage Bucket Privacy:** In Supabase Dashboard $\to$ Storage, confirm that bucket `student-profiles` has **Public Bucket = OFF**.

---

## 8. Exact Commands for Dry Run and Actual Migration

### Step A: Execute Pre-Flight Inspection (Read-Only)
```powershell
python backend/migration/inspect_source.py
```

### Step B: Execute Dry-Run Simulation (MANDATORY Before Live Migration)
```powershell
python backend/migration/migrate_to_supabase.py --dry-run
```
*Review the terminal summary. Confirm that all tables report `VALIDATED_FOR_INSERT` and 0 errors.*

### Step C: Execute Live Cloud Migration (Only After You Review & Approve)
```powershell
python backend/migration/migrate_to_supabase.py --execute
```

### Step D: Execute Comprehensive Verification Audit
```powershell
python backend/migration/verify_migration.py
```
*Confirm output displays:*  
`FINAL AUDIT RESULT: VERIFICATION PASSED: Database & biometrics migrated with 100% fidelity.`

---

## 9. Rollback & Disaster Recovery Reference

If you ever need to rollback or restore:
1. **Instant Application Revert:** Change `DATABASE_URL` in `backend/.env` back to `sqlite:///./smart_hostel.db` and set `ENVIRONMENT=development`. The backend immediately reads from local SQLite.
2. **Restore from Phase 1 Backup:**
   ```powershell
   Copy-Item "D:\Hostel_Cloud_Migration_Backup\Before_Supabase_Migration\smart_hostel.db" "D:\Proto Studio I\backend\smart_hostel.db" -Force
   Copy-Item "D:\Hostel_Cloud_Migration_Backup\Before_Supabase_Migration\profiles\*" "D:\Proto Studio I\backend\app\uploads\profiles\" -Force
   ```
