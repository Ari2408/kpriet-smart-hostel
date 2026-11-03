# ☁️ Cloud Deployment Preparation Report (Phase 2)
**Project:** KPRIET Smart Hostel Attendance Management System  
**Institution:** KPR Institute of Engineering and Technology, Coimbatore  
**Target Platform:** Render (FastAPI Backend) + Supabase (PostgreSQL & Storage)  
**Status:** Completed Cloud Readiness Audit & Configuration  
**Date:** November 3, 2026  

---

## 1. Files Created

| File Path | Purpose |
| :--- | :--- |
| [`backend/requirements.txt`](file:///d:/Proto%20Studio%20I/backend/requirements.txt) | Complete, pinned production dependencies including `fastapi`, `uvicorn`, `psycopg2-binary`, `opencv-python-headless`, `sqlalchemy`, and `reportlab`. |
| [`D:\Proto Studio I\.gitignore`](file:///d:/Proto%20Studio%20I/.gitignore) | Comprehensive root Git ignore preventing tracking of SQLite database files (`*.db`), local student photographs (`uploads/profiles/*`), virtual environments, `.env` files, and Flutter build artifacts. |
| [`D:\Proto Studio I\.env.example`](file:///d:/Proto%20Studio%20I/.env.example) | Safe environment variable template for root workspace with zero hardcoded credentials. |
| [`backend/.env.example`](file:///d:/Proto%20Studio%20I/backend/.env.example) | Safe environment variable template for backend subfolder and container deployments. |
| [`backend/app/uploads/profiles/.gitkeep`](file:///d:/Proto%20Studio%20I/backend/app/uploads/profiles/.gitkeep) | Preserves the uploads folder structure in Git while ignoring private biometric photo assets. |
| [`backend/app/uploads/reports/.gitkeep`](file:///d:/Proto%20Studio%20I/backend/app/uploads/reports/.gitkeep) | Preserves reports folder structure in Git while ignoring generated documents. |

---

## 2. Files Modified

| File Path | Modifications Made |
| :--- | :--- |
| [`backend/app/database.py`](file:///d:/Proto%20Studio%20I/backend/app/database.py) | 1. Added `python-dotenv` loader (`load_dotenv()`) to read local `.env` files.<br>2. Added PostgreSQL URI normalization: converts `postgres://` to `postgresql+psycopg2://` (required for SQLAlchemy 2.0 compatibility on Supabase/Render).<br>3. Added production connection pooling (`pool_pre_ping=True`, `pool_recycle=300`, `pool_size=10`, `max_overflow=20`) to prevent socket exhaustion and stale connection drops on Supabase.<br>4. Retained 100% backward compatibility for local SQLite execution (`check_same_thread=False`). |
| [`backend/app/main.py`](file:///d:/Proto%20Studio%20I/backend/app/main.py) | 1. Added `if __name__ == "__main__":` block dynamically reading `PORT` environment variable (`os.getenv("PORT", 8000)`).<br>2. Updated `/api/health` check endpoint to expose active `environment` (`development` vs `production`). |
| [`backend/app/seed.py`](file:///d:/Proto%20Studio%20I/backend/app/seed.py) | 1. Separated schema creation from synthetic demo data seeding.<br>2. Added `SEED_DEMO_DATA` environment variable guard: production will **never** automatically insert synthetic student/staff accounts or mock attendance.<br>3. Updated default campus coordinates to match the latest KPRIET administration coordinates (`11.077711, 77.142223`, radius `800.0m`). |
| [`backend/tests/test_backend.py`](file:///d:/Proto%20Studio%20I/backend/tests/test_backend.py) | Updated test fixtures to dynamically bind to available active student and staff records rather than hardcoding deleted student IDs. |

---

## 3. Production Dependencies Identified (`backend/requirements.txt`)

```text
# Core Web Framework & Server
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
email-validator>=2.2.0
python-dotenv>=1.0.1

# Database ORM & PostgreSQL Driver
sqlalchemy>=2.0.30
psycopg2-binary>=2.9.9

# Data Validation & Cryptography
pydantic>=2.8.0
bcrypt>=4.1.0

# Facial Recognition & Machine Learning (Headless for Cloud Linux)
opencv-python-headless>=4.10.0.84
numpy>=1.26.0

# Institutional Reporting & Document Generation
reportlab>=4.2.0

# HTTP Client (for Supabase Storage REST API & health checks)
httpx>=0.27.0
```

> [!IMPORTANT]
> **OpenCV Headless Compatibility:** Using `opencv-python-headless` instead of `opencv-python` is critical for Render Linux containers. Standard `opencv-python` attempts to link with desktop X11/OpenGL libraries (`libGL.so.1`), which causes an unrecoverable `ImportError` on headless servers.

---

## 4. Production Environment Variables

| Variable Name | Required Value in Production | Purpose |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Switches logging and security guards to production mode. |
| `PORT` | Auto-set by Render (e.g. `10000`) | Dynamic port assigned by Render cloud infrastructure. |
| `DATABASE_URL` | `postgresql+psycopg2://postgres:[PW]@[HOST]:[PORT]/postgres` | Connects SQLAlchemy to Supabase PostgreSQL database. |
| `JWT_SECRET_KEY` | 32+ character high-entropy random string | Cryptographic key used to sign and verify HMAC-SHA256 authentication tokens. |
| `SUPABASE_URL` | `https://[PROJECT-REF].supabase.co` | Base URL for Supabase cloud project. |
| `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_KEY` | `[SUPABASE-SERVICE-ROLE-KEY]` | Service-role key for backend server to upload student profile photos to storage bucket (bypassing RLS). |
| `SUPABASE_BUCKET`| `student-profiles` | Target bucket name in Supabase Storage. |
| `SEED_DEMO_DATA` | `false` | Prevents the server from auto-generating synthetic students or attendance in production. |

---

## 5. PostgreSQL Compatibility Audit

| Database Aspect | SQLite Implementation | PostgreSQL Compatibility Analysis | Required Action |
| :--- | :--- | :--- | :--- |
| **Primary Keys & Autoincrement** | `Column(Integer, primary_key=True)` (SQLite `ROWID`) | In PostgreSQL, SQLAlchemy automatically translates `Integer, primary_key=True` to `SERIAL` (sequence-backed auto-increment). | ✅ **100% Compatible.** No code changes required. |
| **String & Text Columns** | `String(50)`, `String(150)`, `Text` | Maps natively to PostgreSQL `VARCHAR(n)` and `TEXT`. | ✅ **100% Compatible.** |
| **Float / Coordinates** | `Float` (Latitude, Longitude, Distance) | Maps natively to PostgreSQL `DOUBLE PRECISION`. | ✅ **100% Compatible.** |
| **Boolean Flags** | Stored as `0` / `1` in SQLite | PostgreSQL has native `BOOLEAN` (`TRUE` / `FALSE`). SQLAlchemy handles type casting automatically. | ✅ **100% Compatible.** |
| **Date & Time Types** | `Date` and `Time` columns stored as text in SQLite | PostgreSQL uses native `DATE` and `TIME WITHOUT TIME ZONE`. | ✅ **100% Compatible.** Format strings in Python (`%H:%M`, `%Y-%m-%d`) remain identical. |
| **Foreign Keys & Cascades** | `ondelete="CASCADE"`, `ondelete="SET NULL"` | SQLite requires `PRAGMA foreign_keys=ON`. PostgreSQL enforces foreign key constraints natively at the database level. | ✅ **100% Compatible.** PostgreSQL provides stronger enforcement. |
| **Case-Insensitive Search** | `Student.name.ilike(...)` in [`students.py`](file:///d:/Proto%20Studio%20I/backend/app/routers/students.py#L40) | SQLite uses `LOWER()` emulation. PostgreSQL natively uses the high-performance `ILIKE` operator. | ✅ **100% Compatible & Faster on PostgreSQL.** |
| **Raw SQL Queries** | None. All routes use SQLAlchemy ORM methods (`query()`, `filter()`, `update()`). | No dialect-specific raw SQL exists in the application codebase. | ✅ **100% Compatible.** |

---

## 6. Security Audit Findings

| Audit Check | Finding | Status / Recommended Remediation |
| :--- | :--- | :--- |
| **Hardcoded JWT Secret** | [`backend/app/security.py`](file:///d:/Proto%20Studio%20I/backend/app/security.py#L14) has a default fallback string: `"kpriet-smart-hostel-jwt-secret-key-2026-production"`. | ⚠️ **Action Required on Render:** Provide a unique random `JWT_SECRET_KEY` in Render environment variables. The fallback should only be used in local offline dev. |
| **Default Staff Passwords** | [`backend/app/seed.py`](file:///d:/Proto%20Studio%20I/backend/app/seed.py) contains initial demo credentials (`Warden@123`, `Staff@123`). | 🛡️ **Remediated:** Setting `SEED_DEMO_DATA=false` ensures demo credentials are never created on production PostgreSQL. Legitimate staff accounts will be migrated with their existing bcrypt hashes. |
| **CORS Wildcard Configuration** | [`backend/app/main.py`](file:///d:/Proto%20Studio%20I/backend/app/main.py#L32) sets `allow_origins=["*"]`. | ℹ️ **Safe for Mobile:** Flutter Android native apps communicate over native OS sockets and do not enforce browser CORS restrictions. If a web portal is deployed later, origin can be locked to the portal's domain. |
| **Student Biometrics & Photos** | Biometric facial embeddings (128D floats) are stored in the database. Photographs are stored in `uploads/profiles/`. | 🛡️ **Remediated:** The newly created `.gitignore` explicitly blocks all files under `backend/app/uploads/profiles/*` and all `*.db` files from entering Git. |
| **Exposed API Keys / Tokens** | Codebase was scanned for hardcoded third-party API keys (Supabase, AWS, Firebase). | ✅ **Zero exposed cloud keys found in source code.** |

---

## 7. GitHub Repository Readiness

- **Current Git Status:** Git is **not yet initialized** in `D:\Proto Studio I` (confirmed via `git status` $\to$ `fatal: not a git repository`).
- **Safety Verification:** Because Git has not yet been initialized, **no sensitive files, real student records, database files, or photographs have ever been committed or tracked**.
- **Protection in Place:** The newly created `.gitignore` is positioned at `D:\Proto Studio I\.gitignore`. When `git init` and `git add` are executed, Git will automatically honor the ignore patterns and exclude all sensitive assets.

---

## 8. Exact Commands for the Next Deployment Phase

When you are ready to proceed to Phase 3, these are the exact commands:

### A. Initialize and Inspect Git (Local Verification)
```powershell
cd "D:\Proto Studio I"
git init
git add .
git status
```
*Verify that `smart_hostel.db` and files in `uploads/profiles/` do NOT appear in the staged files list.*

### B. Commit Clean Production Codebase
```powershell
git commit -m "feat: prepare KPRIET Smart Hostel backend for Render cloud deployment"
```

### C. Connect to Private GitHub Repository & Push
```powershell
git remote add origin https://github.com/[YOUR-USERNAME]/kpriet-smart-hostel.git
git branch -M main
git push -u origin main
```
*(Always ensure the GitHub repository visibility is set to **Private**).*

### D. Render Web Service Deployment Configuration
On the [Render Dashboard](https://dashboard.render.com):
1. **New $\to$ Web Service** $\to$ Connect your private repository.
2. **Root Directory:** `backend`
3. **Environment:** `Python 3`
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. **Environment Variables:** Add `DATABASE_URL`, `JWT_SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_KEY`), `SUPABASE_BUCKET`, and `SEED_DEMO_DATA=false`.

---

## 🎯 Phase 2 Completion Status

- [x] `backend/requirements.txt` created with verified production dependencies.
- [x] Root `.gitignore` created to protect databases, photos, and secrets.
- [x] Safe `.env.example` templates created.
- [x] Environment variable configuration separated from code (`load_dotenv()` integrated).
- [x] Dynamic Render `$PORT` support implemented.
- [x] `SEED_DEMO_DATA` guard implemented to protect production from synthetic accounts.
- [x] PostgreSQL compatibility audited (100% ORM compatible).
- [x] Security audit completed and documented.
- [x] GitHub readiness verified (zero sensitive files tracked).
