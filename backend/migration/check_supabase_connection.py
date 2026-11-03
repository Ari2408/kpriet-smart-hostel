#!/usr/bin/env python3
"""
check_supabase_connection.py - Read-Only Supabase Connectivity Diagnostic Tool
Part of the KPRIET Smart Hostel Cloud Migration Suite.

Performs 100% READ-ONLY diagnostic checks:
1. Environment variables verification (DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET)
2. Supabase project API endpoint availability
3. Supabase PostgreSQL SSL connection (executes strictly 'SELECT 1')
4. Supabase Private Storage bucket existence ("student-profiles")
5. Storage bucket privacy enforcement ("public == false")

SAFETY GUARANTEES:
- Zero database writes, modifications, or table creation.
- Zero file uploads, downloads, or deletions.
- Passwords, connection strings, and service keys are automatically masked.
- Returns exit code 0 if all checks pass, exit code 1 if any check fails.
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# Try importing httpx
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# Try importing sqlalchemy
try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

# Base paths
MIGRATION_DIR = Path(__file__).resolve().parent
BACKEND_DIR = MIGRATION_DIR.parent
DEFAULT_ENV_FILE = BACKEND_DIR / ".env"
FALLBACK_ENV_FILE = BACKEND_DIR.parent / ".env"

def mask_connection_string(conn_str: str) -> str:
    """Masks database passwords in connection URLs for safe logging."""
    if not conn_str:
        return "<not set>"
    # Mask password between colon and @
    masked = re.sub(r":([^/@:]+)@", r":****@", conn_str)
    return masked

def mask_secret(secret: str) -> str:
    """Masks API keys and secrets (e.g. eyJ...****)."""
    if not secret:
        return "<not set>"
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}...{secret[-4:]}"

def normalize_database_url(url: Optional[str]) -> Optional[str]:
    """
    Normalizes PostgreSQL connection strings for SQLAlchemy 2.0 and Supabase SSL:
    - postgres:// -> postgresql+psycopg2://
    - postgresql:// -> postgresql+psycopg2://
    - Enforces sslmode=require for remote cloud connections.
    """
    if not url:
        return None
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # Ensure sslmode=require for remote hosts
    if url.startswith("postgresql+") and "localhost" not in url and "127.0.0.1" not in url:
        if "sslmode=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
    return url

def check_environment_variables(env_file_path: Path) -> Tuple[bool, Dict[str, Any], str]:
    """Check 1: Loads and validates required environment variables."""
    if env_file_path.exists():
        load_dotenv(env_file_path)
    elif FALLBACK_ENV_FILE.exists():
        load_dotenv(FALLBACK_ENV_FILE)
    else:
        # Load from current system environment
        load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or
        os.getenv("SUPABASE_SERVICE_KEY") or
        os.getenv("SUPABASE_KEY")
    )
    bucket_name = os.getenv("SUPABASE_BUCKET", "student-profiles")

    missing = []
    if not db_url or "sqlite" in db_url.lower():
        missing.append("DATABASE_URL (must be a Supabase PostgreSQL URL, not SQLite)")
    if not supabase_url or not supabase_url.startswith("http"):
        missing.append("SUPABASE_URL (must start with https://)")
    if not supabase_key or len(supabase_key) < 20:
        missing.append("SUPABASE_SERVICE_ROLE_KEY (missing or invalid length)")

    config = {
        "env_file": str(env_file_path) if env_file_path.exists() else "<loaded from environment>",
        "database_url_masked": mask_connection_string(db_url or ""),
        "supabase_url": supabase_url or "<not set>",
        "supabase_key_masked": mask_secret(supabase_key or ""),
        "supabase_bucket": bucket_name,
        "raw_db_url": db_url,
        "raw_supabase_url": supabase_url,
        "raw_supabase_key": supabase_key,
    }

    if missing:
        return False, config, f"Missing or placeholder configuration: {', '.join(missing)}"
    return True, config, "All required environment variables are configured."

def check_supabase_api_endpoint(supabase_url: str, supabase_key: str) -> Tuple[bool, str]:
    """Check 2: Verifies Supabase API / Auth health endpoint responds."""
    if not HAS_HTTPX:
        return False, "httpx library not installed. Run: pip install httpx"

    endpoint = f"{supabase_url.rstrip('/')}/auth/v1/health"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint, headers=headers)
            if resp.status_code == 200:
                return True, f"Supabase project API is healthy and reachable (HTTP {resp.status_code})."
            # Fallback to checking root REST endpoint
            rest_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/"
            resp_rest = client.get(rest_endpoint, headers=headers)
            if resp_rest.status_code == 200:
                return True, f"Supabase REST endpoint is reachable (HTTP {resp_rest.status_code})."
            return False, f"Supabase endpoint responded with HTTP {resp.status_code}."
    except Exception as e:
        safe_msg = mask_connection_string(str(e))
        return False, f"Failed to connect to Supabase endpoint: {safe_msg}"

def check_postgresql_connection(db_url: str) -> Tuple[bool, str]:
    """Check 3: Connects via SSL and executes strictly 'SELECT 1;'."""
    if not HAS_SQLALCHEMY:
        return False, "SQLAlchemy not installed. Run: pip install sqlalchemy"

    norm_url = normalize_database_url(db_url)
    if not norm_url:
        return False, "Invalid or missing DATABASE_URL"

    try:
        # Explicit timeout to avoid hanging on firewall blocks
        engine = create_engine(
            norm_url,
            connect_args={"connect_timeout": 10},
            pool_pre_ping=True
        )
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result == 1:
                return True, "Successfully connected to PostgreSQL via SSL and verified 'SELECT 1'."
            return False, f"Unexpected query result from 'SELECT 1': {result}"
    except Exception as e:
        safe_err = mask_connection_string(str(e))
        if "No module named 'psycopg2'" in safe_err:
            return False, "PostgreSQL driver 'psycopg2' not found. Run: pip install psycopg2-binary"
        return False, f"PostgreSQL connection failed: {safe_err}"

def check_storage_bucket_exists(supabase_url: str, supabase_key: str, bucket: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Check 4: Verifies the target private storage bucket exists."""
    if not HAS_HTTPX:
        return False, None, "httpx library not installed. Run: pip install httpx"

    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/bucket/{bucket}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint, headers=headers)
            if resp.status_code == 200:
                bucket_info = resp.json()
                return True, bucket_info, f"Storage bucket '{bucket}' exists."
            elif resp.status_code == 404:
                return False, None, f"Storage bucket '{bucket}' was NOT found on this Supabase project."
            else:
                return False, None, f"Failed to inspect bucket '{bucket}': HTTP {resp.status_code}."
    except Exception as e:
        safe_msg = mask_connection_string(str(e))
        return False, None, f"Storage bucket request exception: {safe_msg}"

def check_bucket_privacy(bucket_info: Optional[Dict[str, Any]], bucket_name: str) -> Tuple[bool, str]:
    """Check 5: Verifies that public == false."""
    if not bucket_info:
        return False, f"Cannot verify privacy of bucket '{bucket_name}' because bucket was not found."

    is_public = bucket_info.get("public", False)
    if is_public:
        return False, f"SECURITY ALERT: Bucket '{bucket_name}' is set to PUBLIC! It must be set to PRIVATE (public=false)."
    return True, f"Bucket '{bucket_name}' is verified PRIVATE (public=false)."

def run_diagnostics(env_file_path: Path) -> Dict[str, Any]:
    """Runs all 5 read-only connectivity checks."""
    report = {
        "summary": "PENDING",
        "checks": {},
        "all_passed": False
    }

    # Check 1: Environment Variables
    c1_ok, config, c1_msg = check_environment_variables(env_file_path)
    report["checks"]["1_environment_configuration"] = {
        "name": "Environment Variables (.env)",
        "status": "PASS" if c1_ok else "FAIL",
        "details": c1_msg,
        "database_url": config["database_url_masked"],
        "supabase_url": config["supabase_url"],
        "supabase_key": config["supabase_key_masked"],
        "supabase_bucket": config["supabase_bucket"],
    }

    # If Check 1 failed due to missing credentials, skip network checks
    if not c1_ok:
        report["checks"]["2_supabase_api_endpoint"] = {"status": "SKIP", "details": "Skipped due to missing SUPABASE_URL"}
        report["checks"]["3_postgresql_connection"] = {"status": "SKIP", "details": "Skipped due to missing DATABASE_URL"}
        report["checks"]["4_storage_bucket_exists"] = {"status": "SKIP", "details": "Skipped due to missing credentials"}
        report["checks"]["5_storage_bucket_privacy"] = {"status": "SKIP", "details": "Skipped due to missing credentials"}
        report["summary"] = "FAIL - Environment variables missing or incomplete."
        report["all_passed"] = False
        return report

    # Check 2: Supabase API Endpoint
    c2_ok, c2_msg = check_supabase_api_endpoint(config["raw_supabase_url"], config["raw_supabase_key"])
    report["checks"]["2_supabase_api_endpoint"] = {
        "name": "Supabase API Endpoint Health",
        "status": "PASS" if c2_ok else "FAIL",
        "details": c2_msg,
    }

    # Check 3: PostgreSQL SSL Connection (SELECT 1)
    c3_ok, c3_msg = check_postgresql_connection(config["raw_db_url"])
    report["checks"]["3_postgresql_connection"] = {
        "name": "Supabase PostgreSQL SSL Connection (SELECT 1)",
        "status": "PASS" if c3_ok else "FAIL",
        "details": c3_msg,
    }

    # Check 4: Storage Bucket Existence
    c4_ok, bucket_info, c4_msg = check_storage_bucket_exists(
        config["raw_supabase_url"], config["raw_supabase_key"], config["supabase_bucket"]
    )
    report["checks"]["4_storage_bucket_exists"] = {
        "name": f"Storage Bucket Existence ('{config['supabase_bucket']}')",
        "status": "PASS" if c4_ok else "FAIL",
        "details": c4_msg,
    }

    # Check 5: Storage Bucket Privacy (public == false)
    c5_ok, c5_msg = check_bucket_privacy(bucket_info, config["supabase_bucket"])
    report["checks"]["5_storage_bucket_privacy"] = {
        "name": f"Storage Bucket Privacy (public=false)",
        "status": "PASS" if c5_ok else "FAIL",
        "details": c5_msg,
    }

    all_ok = c1_ok and c2_ok and c3_ok and c4_ok and c5_ok
    report["all_passed"] = all_ok
    report["summary"] = "ALL CHECKS PASSED - Supabase is fully reachable and correctly configured." if all_ok else "ONE OR MORE CHECKS FAILED."
    return report

def print_report(report: Dict[str, Any]):
    print("=" * 80)
    print("  KPRIET SMART HOSTEL - SUPABASE CONNECTIVITY DIAGNOSTIC (READ-ONLY)")
    print("=" * 80)
    for key, check in sorted(report["checks"].items()):
        status_box = f"[{check['status']}]"
        print(f"  {status_box:<8} {check.get('name', key)}")
        print(f"           Details : {check['details']}")
        if "database_url" in check:
            print(f"           Database: {check['database_url']}")
            print(f"           Endpoint: {check['supabase_url']}")
            print(f"           Key     : {check['supabase_key']}")
            print(f"           Bucket  : {check['supabase_bucket']}")
        print("-" * 80)

    verdict = "[PASS] ALL CHECKS PASSED: Supabase connectivity and bucket privacy verified." if report["all_passed"] else "[FAIL] DIAGNOSTIC FAILED: Resolve reported issues before attempting cloud migration."
    print(f"VERDICT: {verdict}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="KPRIET Smart Hostel Supabase Read-Only Connectivity Diagnostic")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Path to .env file")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    args = parser.parse_args()

    report = run_diagnostics(args.env_file)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    # Exit with code 0 on success, code 1 on failure
    sys.exit(0 if report["all_passed"] else 1)

if __name__ == "__main__":
    main()
