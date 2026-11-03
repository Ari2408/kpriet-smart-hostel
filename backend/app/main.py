import os
import re
from typing import Optional, Dict, Any
from fastapi import FastAPI, Response, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import engine, Base, get_db
from .models import Student
from .security import decode_access_token, security_bearer
from .seed import seed_database
from .routers import auth, students, attendance, reports, config

# Create tables
Base.metadata.create_all(bind=engine)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] Initializing database and verifying seed data...")
    seed_database()
    print("[Startup] Ready to accept requests.")
    yield

app = FastAPI(
    title="Smart Hostel Attendance Management System API",
    description="Backend API for Facial Recognition & GPS Geofenced Attendance at KPR Institute of Engineering and Technology",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving & Secure Cloud Storage Proxy for Student Photographs
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+\.(jpg|jpeg|png)$")

@app.get("/uploads/profiles/{filename}")
def get_profile_photo(
    filename: str,
    token: Optional[str] = Query(None, description="JWT authentication token for image loading"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
):
    """
    Authenticated & Authorized Retrieval of Student Photographs:
    1. Input Validation: Strictly validates filename against whitelist pattern and prevents path traversal.
    2. Authentication: Requires valid JWT (via HTTP Authorization Bearer header or '?token=' query parameter).
    3. Authorization:
       - Staff / Warden / Admin: Can access any student photograph.
       - Student: Can ONLY access their own photograph (enforced via DB ownership check).
       - Other: 403 Forbidden.
    4. Private Cache Policy: Emits 'Cache-Control: private, no-cache, no-store, must-revalidate' (no public cache exposure).
    5. Storage Retrieval:
       - Checks local disk inside designated profiles folder.
       - In cloud production, securely streams from Supabase Private Storage using server-side credentials.
    6. Information Leakage Prevention: Never returns raw cloud storage errors or secrets to clients.
    """
    # 1. Filename validation & path traversal prevention
    if not filename or not FILENAME_PATTERN.match(filename) or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename format. Only alphanumeric characters, dashes, underscores, and .jpg/.png are permitted."
        )

    clean_filename = os.path.basename(filename)

    # 2. Authentication: Extract and verify JWT token from Header or Query Param
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required to access student biometric photographs.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    current_user = decode_access_token(raw_token)

    # 3. Authorization: Role and ownership check
    student = db.query(Student).filter(
        (Student.profile_photo_url.like(f"%{clean_filename}")) |
        (Student.register_number == clean_filename.split("_")[0])
    ).first()

    user_role = current_user.get("role")

    if user_role in ("staff", "admin", "warden"):
        # Authorized staff/warden can view all student photographs
        pass
    elif user_role == "student":
        # Students can ONLY access their own photograph
        user_sub = str(current_user.get("sub", ""))
        user_identifier = str(current_user.get("identifier", ""))

        is_owner = False
        if student:
            if str(student.id) == user_sub or student.register_number == user_identifier:
                is_owner = True
        elif clean_filename.startswith(f"{user_identifier}_"):
            is_owner = True

        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students are only authorized to view their own profile photograph."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to authorized personnel or photo owner."
        )

    # 4. Strict Private Caching Policy (Never public)
    cache_headers = {
        "Cache-Control": "private, no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    # 5. Safe Local Disk Retrieval
    local_path = os.path.abspath(os.path.join(UPLOAD_DIR, "profiles", clean_filename))
    expected_dir = os.path.abspath(os.path.join(UPLOAD_DIR, "profiles"))
    if not local_path.startswith(expected_dir):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path.")

    if os.path.exists(local_path) and os.path.isfile(local_path):
        return FileResponse(local_path, media_type="image/jpeg", headers=cache_headers)

    # 6. Secure Supabase Private Storage Streaming (Server-side service credentials only)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    supabase_bucket = os.getenv("SUPABASE_BUCKET", "student-profiles")

    if supabase_url and supabase_key:
        try:
            import httpx
            endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/authenticated/{supabase_bucket}/{clean_filename}"
            auth_headers = {
                "Authorization": f"Bearer {supabase_key}",
                "apiKey": supabase_key,
            }
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(endpoint, headers=auth_headers)
                if resp.status_code == 200:
                    media_type = resp.headers.get("content-type", "image/jpeg")
                    return Response(
                        content=resp.content,
                        media_type=media_type,
                        headers=cache_headers
                    )
        except Exception:
            # Mask internal errors: never return cloud secrets or internal errors
            pass

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Student profile photograph not found."
    )

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Include Routers
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(reports.router)
app.include_router(config.router)

@app.get("/")
def root():
    return {
        "institution": "KPR Institute of Engineering and Technology",
        "system": "Smart Hostel Attendance Management System",
        "status": "online",
        "docs_url": "/docs"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Smart Hostel Attendance API",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
