# KPRIET Smart Hostel Attendance Management System
# Render Cloud Deployment Readiness & Pre-Flight Security Audit Report

**Date:** November 3, 2026  
**Institution:** KPR Institute of Engineering and Technology, Coimbatore  
**Target Platform:** Render Cloud Platform (Linux Web Service)  
**Backend Directory:** `backend/`  
**Overall Readiness Verdict:** **READY FOR DEPLOYMENT WITH 2 REQUIRED PRE-FLIGHT FIXES**  

---

## Executive Summary

An exhaustive, read-only pre-flight inspection of the KPRIET Smart Hostel backend was performed to assess cloud readiness for deployment on Render. The Supabase cloud PostgreSQL migration and verification suites have completed successfully.

All 12 items specified in the deployment criteria were thoroughly evaluated against the actual codebase:
- **8 Checks PASSED** (Dependencies, Entrypoint, Host/Port Binding, JWT Security, Server-Side Secret Isolation, Demo Seeding Control, Photo Security Proxy, and Render Config).
- **2 Checks flagged as WARNING** (Database SQLite fallback guard in production; runtime new student photo storage on ephemeral disk).
- **2 Checks flagged as FAIL / ACTION REQUIRED** (Credential scrubbing in `backend/.env.example` before pushing to Git; missing production SQLite rejection guard in `database.py`).

---

## Detailed Check-by-Check Evaluation Matrix

| Check # | Item Inspected | Verdict | Summary / Impact |
| :---: | :--- | :---: | :--- |
| **1** | Production Dependencies in `backend/requirements.txt` | **PASS** | Contains all 13 required packages (`psycopg2-binary`, `opencv-python-headless`, etc.). No duplicate or GUI OpenCV packages. |
| **2** | FastAPI Application Entrypoint (`app.main:app`) | **PASS** | FastAPI instance `app` is instantiated at module scope in `backend/app/main.py`. |
| **3** | Host & Port Binding (`0.0.0.0` & `$PORT`) | **PASS** | Binds to `0.0.0.0` and dynamically reads `os.getenv("PORT", 8000)`. |
| **4** | `DATABASE_URL` Production Fallback Guard | **WARNING / FAIL** | `database.py` reads `DATABASE_URL`, but falls back to SQLite default without raising an error if `ENVIRONMENT=production`. |
| **5** | Mandatory `JWT_SECRET_KEY` Production Enforcement | **PASS** | `security.py` strictly refuses to start in production if `JWT_SECRET_KEY` is missing, placeholder, or `< 32` characters. |
| **6** | Supabase Secrets Backend-Only Isolation | **PASS** | `SUPABASE_SERVICE_ROLE_KEY` is read only server-side. Zero Supabase credentials or SDKs exist in the Flutter app. |
| **7** | `SEED_DEMO_DATA` Default Behavior in Production | **PASS** | Defaults to `"false"` in `seed.py`. Synthetic demo records are never inserted in production. |
| **8** | CORS Configuration | **PASS / WARNING** | Configured with `allow_origins=["*"]`. Fully functional for Flutter mobile; recommendation provided for web browsers. |
| **9** | Photo Authentication & Private Storage Access | **PASS** | `/uploads/profiles/{filename}` validates filenames, enforces JWT role/ownership authorization, and streams from private storage. |
| **10** | Ephemeral Filesystem Compatibility | **WARNING** | PostgreSQL and memory-buffered reports are 100% ephemeral-safe. New student registrations at runtime write to local disk. |
| **11** | Git Exclusions & Sensitive Files (`.gitignore`) | **FAIL (ACTION)** | `.gitignore` rules correctly ignore `.env` and `.db`. **CRITICAL:** `backend/.env.example` contains live credentials and must be scrubbed! |
| **12** | Render Environment Variable Coverage | **PASS** | All required environment variables can be configured directly in Render Dashboard. |

---

## Detailed Audit Findings

### Check 1: Production Dependencies (`backend/requirements.txt`)
**Verdict: PASS**
- **File:** `backend/requirements.txt`
- **Verification:**
  - `fastapi>=0.115.0`
  - `uvicorn[standard]>=0.30.0`
  - `python-multipart>=0.0.9`
  - `email-validator>=2.2.0`
  - `python-dotenv>=1.0.1`
  - `sqlalchemy>=2.0.30`
  - `psycopg2-binary>=2.9.9` (PostgreSQL driver present)
  - `pydantic>=2.8.0`
  - `bcrypt>=4.1.0`
  - `opencv-python-headless>=4.10.0.84` (Headless build prevents missing `libGL.so.1` and X11 errors on Render Linux containers)
  - `numpy>=1.26.0`
  - `reportlab>=4.2.0`
  - `httpx>=0.27.0` (Client for Supabase Storage REST calls)
- **OpenCV Check:** No duplicate `opencv-python` or `opencv-contrib-python` exists.
- **Import Coverage:** Cross-checked against all AST imports across `backend/app/`. Every third-party library is accounted for.

---

### Check 2: FastAPI Entrypoint
**Verdict: PASS**
- **File:** `backend/app/main.py`
- **Verification:**
  - `app = FastAPI(...)` is instantiated at the module level in `backend/app/main.py`.
  - When the Root Directory is set to `backend` on Render, the entrypoint string is `app.main:app`.
  - Verified start command compatibility: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

---

### Check 3: Host & Port Binding
**Verdict: PASS**
- **File:** `backend/app/main.py` (lines 205–208)
- **Verification:**
  ```python
  if __name__ == "__main__":
      import uvicorn
      port = int(os.getenv("PORT", 8000))
      uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
  ```
  - Binds to `0.0.0.0`, allowing Render's port forwarder and reverse proxy to route incoming traffic.
  - Dynamically reads `$PORT`, which Render sets automatically (typically port `10000`).

---

### Check 4: `DATABASE_URL` Production Fallback Guard
**Verdict: WARNING / ACTION NEEDED**
- **File:** `backend/app/database.py` (lines 9–15)
- **Current Code:**
  ```python
  DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smart_hostel.db")
  ```
- **Findings:**
  1. `DATABASE_URL` correctly normalizes `postgres://` to `postgresql+psycopg2://` and configures connection pooling (`pool_pre_ping=True`, `pool_recycle=300`).
  2. However, line 9 specifies `"sqlite:///./smart_hostel.db"` as the default fallback.
  3. If a user sets `ENVIRONMENT=production` on Render but forgets to add `DATABASE_URL`, the server will silently create and bind to an ephemeral SQLite database on Render's temporary disk. Any data entered would be lost on container restart.
- **Action Needed:**
  Add a production guard in `backend/app/database.py` so the server refuses to boot if `DATABASE_URL` is omitted in production:
  ```python
  ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
  if ENVIRONMENT in ("production", "prod") and (not os.getenv("DATABASE_URL") or DATABASE_URL.startswith("sqlite")):
      raise RuntimeError(
          "CRITICAL DATABASE CONFIGURATION ERROR: Application started in PRODUCTION mode, "
          "but DATABASE_URL is missing or configured for SQLite! "
          "Set DATABASE_URL to your Supabase PostgreSQL connection string in Render environment variables."
      )
  ```

---

### Check 5: `JWT_SECRET_KEY` Production Enforcement
**Verdict: PASS**
- **File:** `backend/app/security.py` (lines 18–43)
- **Verification:**
  - Evaluates `ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()`.
  - In production (`production` or `prod`), the application checks whether `JWT_SECRET_KEY`:
    1. Is missing or empty string.
    2. Matches known placeholder values (`change-this-to-a-secure...`, `kpriet-smart-hostel-...`, `secret`, `password`, `123456`).
    3. Is shorter than 32 characters.
  - If any check fails, it immediately raises a fatal `RuntimeError` preventing server boot.
  - In local development (`ENVIRONMENT="development"`), fallback is permitted so local offline testing remains functional.

---

### Check 6: Supabase Secrets Backend-Only Isolation
**Verdict: PASS**
- **Files:** `backend/app/main.py`, `smart_hostel_app/lib/`
- **Verification:**
  - `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_URL` are referenced exclusively server-side in `main.py` and the `migration/` scripts.
  - Scanned the entire Flutter frontend (`smart_hostel_app/lib/`): **ZERO** references to Supabase, `SUPABASE_URL`, or `SUPABASE_SERVICE_ROLE_KEY`.
  - The Flutter app communicates solely through the backend API endpoints using Bearer JWT authentication tokens. Service-role credentials are completely isolated from client devices.

---

### Check 7: `SEED_DEMO_DATA` Behavior in Production
**Verdict: PASS**
- **File:** `backend/app/seed.py` (lines 55–60)
- **Verification:**
  ```python
  should_seed_demo = os.getenv("SEED_DEMO_DATA", "false").lower() in ("true", "1", "yes")
  if not should_seed_demo:
      print("[Seed] SEED_DEMO_DATA is disabled or not set. Skipping demo data insertion.")
      return
  ```
  - `SEED_DEMO_DATA` defaults to `"false"`.
  - In production, synthetic demo staff and students are never inserted into the production Supabase database.
  - Institutional data integrity is preserved.

---

### Check 8: CORS Configuration
**Verdict: PASS (for Flutter Mobile) / WARNING (for Web Browsers)**
- **File:** `backend/app/main.py` (lines 36–43)
- **Current Code:**
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Findings:**
  - **Flutter Android/iOS:** Native HTTP clients do not enforce browser CORS policies. Mobile app communication will function seamlessly.
  - **Web Browsers:** W3C CORS specifications disallow `allow_origins=["*"]` when `allow_credentials=True`. While Starlette handles reflection in most cases, browser-based web portals using credentials may encounter warnings.
  - **Recommendation:** If a Web admin portal is deployed in the future, introduce `CORS_ORIGINS` in `.env` to restrict origins to the official domain.

---

### Check 9: Photo Authentication & Private Storage Access
**Verdict: PASS**
- **File:** `backend/app/main.py` (lines 51–177)
- **Verification:**
  - **Filename Whitelisting:** Regex `^[a-zA-Z0-9_\-]+\.(jpg|jpeg|png)$` prevents path traversal (`../`, `\` attacks).
  - **Dual-Mode Authentication:** Accepts JWT via `Authorization: Bearer <token>` or `?token=<token>` (allowing Flutter `Image.network` widget authentication).
  - **Role & Ownership Authorization:**
    - Staff / Warden / Admin can view all student photographs.
    - Students can **only** access their own photograph (verified against `student.id` or `register_number`).
  - **Private Cache Policy:** Sends `Cache-Control: private, no-cache, no-store, must-revalidate` (prevents CDN/browser leakage).
  - **Cloud Proxy:** Streams images from private Supabase Storage bucket (`student-profiles`) using the server's service-role key. Internal storage errors and credentials are never leaked.

---

### Check 10: Ephemeral Filesystem Compatibility
**Verdict: WARNING**
- **Inspection Area:** Database, Reports, and Photo uploads.
- **Findings:**
  - **Database:** Supabase PostgreSQL is external and persistent over network. Ephemeral disk has zero impact on relational records.
  - **Reports:** CSV and PDF exports (`backend/app/routers/reports.py`) are created in-memory via `io.BytesIO()` and streamed directly to clients. Zero disk dependence.
  - **Existing Photos:** All 10 existing referenced photographs were migrated to Supabase Private Storage (`student-profiles`).
  - **Runtime Registration Gap:**
    - In `backend/app/routers/students.py` (lines 101–108), when a warden enrolls a **NEW** student through the API at runtime, the image is decoded and saved to local disk (`UPLOAD_DIR`).
    - The new photo is not automatically forwarded to Supabase Storage at registration time.
    - Because Render's container disk is ephemeral, any student registered *after* initial migration would lose their physical JPEG photo upon container restart (though their 128D facial embedding remains safe in PostgreSQL).
  - **Recommendation:** Add a background helper or direct upload in `students.py` to mirror newly uploaded profile photos directly to Supabase Storage.

---

### Check 11: Git Exclusions & Sensitive Files (`.gitignore`)
**Verdict: FAIL / ACTION REQUIRED**
- **File:** `.gitignore`, `backend/.env.example`
- **Verification:**
  - `.gitignore` properly excludes:
    - `.env` and `.env.*`
    - `*.db` and `backend/smart_hostel.db`
    - `backend/app/uploads/profiles/*` (student photos)
    - `*.keystore` and `local.properties`
- **CRITICAL SECURITY HAZARD FOUND:**
  - `backend/.env.example` currently contains **real plaintext production secrets**, including:
    - A live Supabase PostgreSQL database URL with password.
    - A 64-character JWT secret key.
    - A real, active `SUPABASE_SERVICE_ROLE_KEY`.
  - Because `.gitignore` explicitly allows `.env.example` (`!.env.example`), this file is tracked by Git.
  - **If this project is pushed to GitHub, active production database credentials and service-role keys will be publicly exposed!**
- **Action Required:**
  Before pushing to GitHub, `backend/.env.example` MUST be scrubbed and replaced with generic placeholder values identical to the root `.env.example`.

---

### Check 12: Render Environment Variable Coverage
**Verdict: PASS**
- All parameters needed for cloud operation are fully supported by Render's Environment Variables dashboard.
- Below is the complete configuration checklist for Render.

---

## Render Cloud Deployment Configuration Checklist

When configuring the Web Service in the Render Dashboard (`https://dashboard.render.com`), use the following verified settings:

### Service Settings
| Setting Name | Value to Enter |
| :--- | :--- |
| **Service Type** | Web Service |
| **Language / Runtime** | Python 3 |
| **Region** | Singapore (`singapore`) — closest to KPRIET / Supabase |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Auto-Deploy** | Yes (optional, or manual) |

### Environment Variables to Configure in Render
| Variable Name | Required Value / Format | Purpose |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enables strict security mode |
| `DATABASE_URL` | `postgresql+psycopg2://postgres:[PASSWORD]@[HOST].supabase.co:5432/postgres?sslmode=require` | Supabase PostgreSQL Connection |
| `JWT_SECRET_KEY` | *(Generate a 32+ byte random hex string)* | Cryptographic JWT token signing |
| `SUPABASE_URL` | `https://[PROJECT-REF].supabase.co` | Supabase Cloud REST Endpoint |
| `SUPABASE_SERVICE_ROLE_KEY`| *(Your private Supabase service-role key)* | Server-side private storage proxy |
| `SUPABASE_BUCKET` | `student-profiles` | Target private storage bucket |
| `SEED_DEMO_DATA` | `false` | Prevents inserting dummy data |
| `PORT` | `10000` | Render sets this automatically |

> **How to generate a secure `JWT_SECRET_KEY`:**
> Run this locally in PowerShell:
> ```powershell
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## Required Action Items Before Pushing to GitHub

1. **Scrub `backend/.env.example` (CRITICAL):**
   Replace the real Supabase password and service-role key in `backend/.env.example` with placeholders:
   ```env
   DATABASE_URL=postgresql+psycopg2://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT-HOST].supabase.co:5432/postgres
   JWT_SECRET_KEY=[GENERATE-32-BYTE-HEX-KEY-IN-PRODUCTION]
   SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
   SUPABASE_SERVICE_ROLE_KEY=[YOUR-SUPABASE-SERVICE-ROLE-KEY]
   ```

2. **Add Production SQLite Guard to `backend/app/database.py`:**
   Ensure the backend raises a fatal error if `DATABASE_URL` is missing when `ENVIRONMENT=production`.

3. **Verify Git Status:**
   Confirm that `backend/.env` is NOT staged before running `git push`.
