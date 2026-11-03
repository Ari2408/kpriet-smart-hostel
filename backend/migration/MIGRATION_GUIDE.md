# 🚀 KPRIET Smart Hostel Attendance Management System
## SQLite to Supabase Cloud Migration Guide

**Institution:** KPR Institute of Engineering and Technology, Coimbatore  
**Target Architecture:** Supabase PostgreSQL Database + Supabase Private Storage (`student-profiles`)  
**Source Data:** `backend/smart_hostel.db` (SQLite) + `backend/app/uploads/profiles/` (Biometric Photos)  
**Safety Status:** 100% Non-Destructive | Idempotent | Resumable | Dry-Run by Default  

---

## 1. Migration Architecture & Safety Guarantees

```
┌───────────────────────────────────────────────────────────────┐
│                      LOCAL SOURCE (READ-ONLY)                │
├───────────────────────────────┬───────────────────────────────┤
│    SQLite Database File       │    Local Disk Folder          │
│    "backend/smart_hostel.db"  │    "backend/app/uploads/profiles"
│    (14 Students, 2 Staff,     │    (Biometric Photographs)    │
│     77 Attendance, 6 Logs)    │                               │
└───────────────┬───────────────┴───────────────┬───────────────┘
                │ (Read-Only)                   │ (Read-Only)
                ▼                               ▼
┌───────────────────────────────────────────────────────────────┐
│                   MIGRATION SCRIPTS PIPELINE                  │
│   1. inspect_source.py      ─── Pre-flight audit              │
│   2. migrate_to_supabase.py ─── Dry-Run / Execute migration   │
│   3. verify_migration.py    ─── Post-migration parity audit   │
└───────────────┬───────────────────────────────┬───────────────┘
                │ (SSL PostgreSQL Wire)         │ (HTTPS REST API / Service-Role)
                ▼                               ▼
┌───────────────────────────────┬───────────────────────────────┐
│      SUPABASE POSTGRESQL      │   SUPABASE PRIVATE STORAGE    │
│      Relational Tables        │   Bucket: "student-profiles"  │
│      - Sequences Advanced     │   - Row-Level Security (RLS)  │
│      - Btree Indexes Active   │   - Authenticated Access Only │
└───────────────────────────────┴───────────────────────────────┘
```

### Safety Principles
1. **Source Immutability:** The local SQLite file and photographs are opened in explicit **Read-Only** mode (`?mode=ro`). They will never be deleted, renamed, or modified.
2. **Dry-Run by Default:** The migration script will **never** perform writes or uploads unless the explicit `--execute` flag is passed.
3. **Zero Credential Exposure:** Database passwords and Supabase service-role keys are read exclusively from environment variables or `.env`. Passwords and secrets are automatically masked in all console outputs.
4. **Idempotence & Value-Level Comparison:** On rerun, records are checked by Primary Key (`id`). If values match, the record is skipped cleanly (`identical_skipped`). If values differ, the record is updated (`--on-conflict update`) without creating duplicates.
5. **SQLite-to-PostgreSQL Type Coercion:** Explicitly converts SQLite storage representations to strict PostgreSQL types:
   - Booleans: SQLite `1`/`0` integers are converted to Python `True`/`False` to satisfy PostgreSQL's strict `BOOLEAN` type constraint (resolving `psycopg2.errors.DatatypeMismatch`).
   - Integers & Floats: Verified and preserved as Python `int` and `float`.
   - Dates & Times: Normalized to ISO formats (`YYYY-MM-DD`, `HH:MM:SS`, `YYYY-MM-DD HH:MM:SS.ffffff`).
   - Biometric Data & Hashes: 128D JSON facial embedding strings and `$2b$` bcrypt hashes are preserved character-for-character.
6. **Transactional Atomicity:** Each table migration is executed within a database transaction. Any unexpected error triggers an immediate rollback, preventing partial or inconsistent state.
7. **Sequence Synchronization:** Uses scalar subquery execution:
   ```sql
   SELECT setval(
       pg_get_serial_sequence('<table>', 'id'),
       COALESCE((SELECT MAX(id) FROM <table>), 1),
       (SELECT MAX(id) IS NOT NULL FROM <table>)
   );
   ```
   Works reliably for **both empty and non-empty tables**, ensuring the next inserted record receives the correct incremented ID.
8. **Private Storage Proxy Architecture:** Student photographs remain strictly in the private `student-profiles` bucket. FastAPI exposes a secure streaming proxy at `/uploads/profiles/{filename}` that uses the backend's server-side key. Mobile clients (Flutter) load photos without needing any service-role credentials.

---

## 2. Pre-Requisites & Environment Configuration

### Required Python Packages
Ensure production dependencies are installed in your Python environment:
```powershell
pip install sqlalchemy psycopg2-binary httpx python-dotenv
```

### Environment Variables
Configure your cloud credentials in `backend/.env` (or supply them as environment variables):

```env
# Supabase PostgreSQL Connection String (Transaction Pooler or Direct Connection)
# Note: migrate_to_supabase.py automatically normalizes postgres:// to postgresql+psycopg2:// and enforces sslmode=require
DATABASE_URL=postgresql+psycopg2://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT-HOST].supabase.co:5432/postgres

# Supabase Project Base URL
SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co

# Supabase Service Role Key (Has admin privileges to upload to private storage bucket)
# SECURITY WARNING: NEVER expose this key in Flutter or public repositories!
SUPABASE_SERVICE_ROLE_KEY=[YOUR-SUPABASE-SERVICE-ROLE-KEY]

# Target Private Storage Bucket (Must be configured with public=False)
SUPABASE_BUCKET=student-profiles
```

---

## 3. Step-by-Step Execution Workflow

### Step 1: Pre-Flight Source Inspection (Read-Only)
Run the source database inspector to verify table counts, schema structure, and disk photo inventory:
```powershell
python backend/migration/inspect_source.py
```
*Expected Output:*
- Confirms 6 tables: `system_configs` (1), `staff` (2), `students` (14), `attendance` (77), `verification_sessions` (1), `admin_audit_logs` (6).
- Confirms 14/14 valid 128D facial embeddings and 14/14 valid bcrypt password hashes.
- Reports disk photograph inventory (10 referenced, 0 missing, 6 unreferenced).

---

### Step 2: Supabase Connectivity & Private Bucket Diagnostic (Read-Only)
Run the pre-flight connectivity tool to verify SSL database access, API health, and storage bucket privacy:
```powershell
python backend/migration/check_supabase_connection.py
```
*Expected Output:*
- `[PASS]` Environment Variables (.env)
- `[PASS]` Supabase API Endpoint Health
- `[PASS]` Supabase PostgreSQL SSL Connection (SELECT 1)
- `[PASS]` Storage Bucket Existence ('student-profiles')
- `[PASS]` Storage Bucket Privacy (public=false)

---

### Step 3: Target Database Schema & Conflict Inspection (Read-Only)
Inspect the Supabase PostgreSQL target to check whether application tables already exist and verify it is clean for migration:
```powershell
python backend/migration/inspect_supabase_target.py
```
*Expected Output:*
- Reports presence and row counts for all 6 application tables.
- Reports any unexpected tables or conflicting rows.
- Issues a suitability assessment (`PRISTINE EMPTY TARGET` or `PRE-INITIALIZED CLEAN SCHEMA`).

---

### Step 4: Run Dry-Run Simulation (MANDATORY)
Run the migration script in dry-run mode. This validates database connectivity, simulates data inserts, checks photo readability, and validates table constraints **without writing any data**:
```powershell
python backend/migration/migrate_to_supabase.py --dry-run
```
*Verify that all 6 tables report `VALIDATED_FOR_MIGRATION` and 0 errors are raised.*

---

### Step 5: Execute Live Migration
Once the dry-run output is verified, execute the live migration by supplying the `--execute` flag:
```powershell
python backend/migration/migrate_to_supabase.py --execute
```

**Optional Migration Flags:**
- `--on-conflict update` (default): Detects and updates any differing records on target.
- `--on-conflict skip`: Leaves existing records on target without updating.
- `--skip-photos`: Migrates database tables only without uploading photos.
- `--photos-only`: Uploads photos only without migrating database tables.

**What this step performs:**
1. Verifies that the Supabase Storage bucket is strictly private (`public=False`).
2. Connects to Supabase PostgreSQL and creates tables based on SQLAlchemy models (if not already existing).
3. Migrates records in topological dependency order:
   - `system_configs` $\to$ `staff` $\to$ `students` $\to$ `attendance` $\to$ `verification_sessions` $\to$ `admin_audit_logs`.
4. Uploads student photographs to private `student-profiles` Supabase Storage bucket using `x-upsert: true` and post-verifies upload.
5. Advances PostgreSQL serial sequences (`setval`) for all tables (empty and non-empty).

---

### Step 6: Verify Migration Fidelity & Referential Integrity
Run the comprehensive verification tool to audit the migrated database against the source SQLite database:
```powershell
python backend/migration/verify_migration.py
```

**What this step checks:**
- **Table Row Counts:** Exact 1:1 match between SQLite and PostgreSQL across all 6 tables.
- **Primary Key Parity:** Every ID in SQLite exists in PostgreSQL.
- **Foreign Key Integrity:** 0 orphaned attendance records; 0 orphaned verification sessions.
- **Deep Column Fidelity:** Value-by-value comparison for every single column in all 6 tables:
  - 128D facial embeddings precision check.
  - Bcrypt password hashes character-for-character check.
  - GPS coordinates and distance tolerances.
  - Timestamps, dates, and times.
- **Sequence Health:** All PostgreSQL auto-increment sequences are greater than or equal to `MAX(id)`.
- **Storage Availability & Size:** Pings Supabase Storage API to verify uploaded photos exist in private bucket and match local file size.
- **Bucket Privacy:** Confirms `student-profiles` bucket is not public.

*Required Result:* `FINAL AUDIT RESULT: VERIFICATION PASSED`

---

### Step 7: Switch Application to Cloud PostgreSQL
After verification passes:
1. Set `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_BUCKET`, and `ENVIRONMENT=production` in Render dashboard environment variables.
2. In local `backend/.env`, set `DATABASE_URL` to your Supabase PostgreSQL URI to run locally against the cloud database.
3. Test backend endpoints:
   - `/api/health` $\to$ Returns `"environment": "production"`
   - `/api/students` $\to$ Returns all 14 migrated students
   - `/uploads/profiles/{filename}` $\to$ Securely serves student photo streamed from private cloud storage.
   - `/api/attendance/summary` $\to$ Returns attendance analytics based on 77 migrated records.

---

## 4. Rollback & Disaster Recovery Procedures

If any failure occurs during or after migration:

### Rollback to Local SQLite:
1. In `backend/.env`, revert `DATABASE_URL` to:
   ```env
   DATABASE_URL=sqlite:///./smart_hostel.db
   ENVIRONMENT=development
   ```
2. Restart the FastAPI backend (`python -m app.main` or `run_backend.bat`).
3. The application will instantly revert to reading from the local `smart_hostel.db` with zero data loss.

### Complete Restoration from Phase 1 Backup:
If the local SQLite database is ever damaged by external factors:
1. A pristine backup is preserved at:
   `D:\Hostel_Cloud_Migration_Backup\Before_Supabase_Migration\`
2. To restore:
   ```powershell
   Copy-Item "D:\Hostel_Cloud_Migration_Backup\Before_Supabase_Migration\smart_hostel.db" "D:\Proto Studio I\backend\smart_hostel.db" -Force
   Copy-Item "D:\Hostel_Cloud_Migration_Backup\Before_Supabase_Migration\profiles\*" "D:\Proto Studio I\backend\app\uploads\profiles\" -Force
   ```
3. Re-run `python backend/migration/inspect_source.py` to confirm restoration of all 14 students and 77 attendance records.

---

## 5. Security & Privacy Rules

- **Private Storage Exclusivity:** The `student-profiles` bucket must **never** be made public. Student facial photographs contain institutional Personally Identifiable Information (PII) and biometric data.
- **Service-Role Key Segregation:** The `SUPABASE_SERVICE_ROLE_KEY` bypasses all Row-Level Security policies. It is intended **strictly for server-side operations** (FastAPI and migration scripts). It must **never** be placed in the Flutter client code, Dart assets, or Git.
- **Git Protection:** Ensure `.env` is never added to Git. Keep all temporary logs and exports outside the repository.
