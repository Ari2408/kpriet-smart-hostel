import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import engine, Base
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

# Static file serving for photos and reports
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
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
