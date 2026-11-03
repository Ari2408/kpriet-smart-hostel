import os
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load local .env if present (do not override explicit test/CI environment overrides)
load_dotenv(override=False)

def validate_database_url(url: Optional[str], environment: str = "development") -> str:
    """
    Validates and normalizes DATABASE_URL based on the target execution environment:
    - In PRODUCTION (ENVIRONMENT='production'):
      * DATABASE_URL is strictly mandatory.
      * DATABASE_URL must point to PostgreSQL (rejects SQLite and non-PostgreSQL drivers).
      * Raises RuntimeError if missing or pointing to SQLite to prevent silent data loss on ephemeral disks.
    - In DEVELOPMENT:
      * Supports SQLite fallback for offline development.
      * Normalizes PostgreSQL URLs to SQLAlchemy 2.0 psycopg2 driver if provided.
    """
    env = (environment or "development").strip().lower()
    raw_url = (url or "").strip()

    if env in ("production", "prod"):
        if not raw_url:
            raise RuntimeError(
                "CRITICAL DATABASE CONFIGURATION ERROR: Application started in PRODUCTION mode (ENVIRONMENT='production'), "
                "but DATABASE_URL environment variable is missing! "
                "Render uses an ephemeral filesystem where SQLite data will be wiped on every deploy/restart. "
                "Set DATABASE_URL to your Supabase PostgreSQL connection string in Render environment variables."
            )
        if raw_url.lower().startswith("sqlite"):
            raise RuntimeError(
                "CRITICAL DATABASE CONFIGURATION ERROR: Application started in PRODUCTION mode (ENVIRONMENT='production'), "
                "but DATABASE_URL is configured for SQLite ('sqlite://...')! "
                "Render Web Services use an ephemeral filesystem where local SQLite databases are wiped on container restart. "
                "Production requires a persistent cloud database. Update DATABASE_URL to your Supabase PostgreSQL URI."
            )

    # Apply default for local development if not provided
    if not raw_url:
        raw_url = "sqlite:///./smart_hostel.db"

    # Normalize PostgreSQL URL for SQLAlchemy 2.0 (Supabase/Render often supply postgres://)
    normalized_url = raw_url
    if normalized_url.startswith("postgres://"):
        normalized_url = normalized_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif normalized_url.startswith("postgresql://") and not normalized_url.startswith("postgresql+"):
        normalized_url = normalized_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    if env in ("production", "prod"):
        if not normalized_url.startswith("postgresql+psycopg2://"):
            raise RuntimeError(
                f"CRITICAL DATABASE CONFIGURATION ERROR: Invalid DATABASE_URL protocol in production. "
                f"Expected PostgreSQL ('postgresql://...'), received '{raw_url.split('://')[0]}://...'."
            )

    return normalized_url

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
DATABASE_URL = validate_database_url(os.getenv("DATABASE_URL"), ENVIRONMENT)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    # Production PostgreSQL connection pooling with health pings
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=20,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
