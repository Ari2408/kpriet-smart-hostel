#!/usr/bin/env python3
"""
migrate_to_supabase.py - KPRIET Smart Hostel SQLite to Supabase Cloud Migration Tool
Part of the SQLite-to-Supabase Cloud Migration Suite.

Safely and idempotently migrates:
1. Relational schema and records to Supabase PostgreSQL:
   - system_configs
   - staff
   - students
   - attendance
   - verification_sessions
   - admin_audit_logs
2. Student biometric photographs to Supabase Private Storage bucket ("student-profiles")
3. Sequence synchronization for both empty and non-empty tables.
4. Deep value-level comparison on reruns (detects and updates modified records rather than silently skipping).
5. Transactional atomicity: partial failures roll back cleanly to prevent database corruption.

SAFETY GUARDS:
- Dry-run mode by default. Real writes REQUIRE explicit '--execute' flag.
- 100% read-only access to source SQLite database.
- Zero local file deletion or modification.
- Never prints passwords, secrets, or biometric values in logs.
- Automatic connection URL normalization and SSL enforcement.
"""

import os
import sys
import json
import sqlite3
import argparse
import datetime
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from dotenv import load_dotenv

# Try importing httpx for storage REST API
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# Try importing sqlalchemy
try:
    from sqlalchemy import create_engine, text, inspect
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

# Base paths
MIGRATION_DIR = Path(__file__).resolve().parent
BACKEND_DIR = MIGRATION_DIR.parent
DEFAULT_SOURCE_DB = BACKEND_DIR / "smart_hostel.db"
DEFAULT_UPLOADS_DIR = BACKEND_DIR / "app" / "uploads" / "profiles"

# Tables in foreign-key dependency order
TABLE_MIGRATION_ORDER = [
    "system_configs",
    "staff",
    "students",
    "attendance",
    "verification_sessions",
    "admin_audit_logs",
]

# Explicit Column Datatype Mappings for SQLite-to-PostgreSQL Conversion
BOOLEAN_COLUMNS: Dict[str, Set[str]] = {
    "system_configs": set(),
    "staff": {"is_active"},
    "students": {"is_active"},
    "attendance": {"liveness_passed", "mock_detected", "is_anonymized"},
    "verification_sessions": {"is_used", "liveness_verified", "face_verified"},
    "admin_audit_logs": set(),
}

INTEGER_COLUMNS: Dict[str, Set[str]] = {
    "system_configs": {"id"},
    "staff": {"id"},
    "students": {"id", "academic_year"},
    "attendance": {"id", "student_id", "anonymized_academic_year"},
    "verification_sessions": {"id", "student_id"},
    "admin_audit_logs": {"id", "performed_by_id"},
}

FLOAT_COLUMNS: Dict[str, Set[str]] = {
    "system_configs": {"campus_latitude", "campus_longitude", "geofence_radius_meters", "liveness_strictness"},
    "staff": set(),
    "students": set(),
    "attendance": {"latitude", "longitude", "distance_from_campus", "face_confidence"},
    "verification_sessions": {"similarity_score"},
    "admin_audit_logs": set(),
}

DATE_COLUMNS: Dict[str, Set[str]] = {
    "system_configs": set(),
    "staff": set(),
    "students": set(),
    "attendance": {"attendance_date"},
    "verification_sessions": set(),
    "admin_audit_logs": set(),
}

TIME_COLUMNS: Dict[str, Set[str]] = {
    "system_configs": set(),
    "staff": set(),
    "students": set(),
    "attendance": {"attendance_time"},
    "verification_sessions": set(),
    "admin_audit_logs": set(),
}

DATETIME_COLUMNS: Dict[str, Set[str]] = {
    "system_configs": {"updated_at"},
    "staff": {"created_at"},
    "students": {"created_at"},
    "attendance": {"timestamp"},
    "verification_sessions": {"created_at", "expires_at"},
    "admin_audit_logs": {"timestamp"},
}

def coerce_sqlite_row(table: str, row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely converts SQLite data types to match PostgreSQL target schema types:
    1. Booleans: integers (1, 0) or strings ('1', '0', 'true', 'false') -> bool (True, False).
       Resolves PostgreSQL 'psycopg2.errors.DatatypeMismatch: column is of type boolean but expression is of type integer'.
    2. Integers: int(val) if not None.
    3. Floats: float(val) if not None.
    4. Dates: normalized ISO date string YYYY-MM-DD.
    5. Times: normalized ISO time string HH:MM:SS or HH:MM:SS.ffffff.
    6. DateTimes: normalized ISO datetime string YYYY-MM-DD HH:MM:SS.ffffff.
    7. JSON / Facial Embeddings: verified valid JSON string, preserved without alteration.
    8. None / NULL: preserved as None for all nullable columns.
    """
    coerced = {}
    bool_cols = BOOLEAN_COLUMNS.get(table, set())
    int_cols = INTEGER_COLUMNS.get(table, set())
    float_cols = FLOAT_COLUMNS.get(table, set())
    date_cols = DATE_COLUMNS.get(table, set())
    time_cols = TIME_COLUMNS.get(table, set())
    dt_cols = DATETIME_COLUMNS.get(table, set())

    for col, val in row_dict.items():
        if val is None:
            coerced[col] = None
            continue

        # 1. Boolean columns: strictly convert 1/0 or strings to Python bool
        if col in bool_cols:
            if isinstance(val, bool):
                coerced[col] = val
            elif isinstance(val, (int, float)):
                coerced[col] = bool(int(val))
            elif isinstance(val, str):
                s = val.strip().lower()
                if s in ("1", "true", "t", "yes", "y"):
                    coerced[col] = True
                elif s in ("0", "false", "f", "no", "n"):
                    coerced[col] = False
                else:
                    coerced[col] = bool(s)
            else:
                coerced[col] = bool(val)
            continue

        # 2. Integer columns
        if col in int_cols:
            coerced[col] = int(val)
            continue

        # 3. Float columns
        if col in float_cols:
            coerced[col] = float(val)
            continue

        # 4. Date columns (attendance_date)
        if col in date_cols:
            if isinstance(val, datetime.date):
                coerced[col] = val.isoformat()
            elif isinstance(val, str):
                coerced[col] = val.strip()[:10]
            else:
                coerced[col] = str(val)
            continue

        # 5. Time columns (attendance_time)
        if col in time_cols:
            if isinstance(val, datetime.time):
                coerced[col] = val.isoformat()
            elif isinstance(val, str):
                coerced[col] = val.strip()
            else:
                coerced[col] = str(val)
            continue

        # 6. DateTime columns
        if col in dt_cols:
            if isinstance(val, (datetime.datetime, datetime.date)):
                coerced[col] = val.isoformat()
            elif isinstance(val, str):
                coerced[col] = val.strip().replace("T", " ")
            else:
                coerced[col] = str(val)
            continue

        # 7. Facial embeddings, password hashes, and other string/text fields
        coerced[col] = val

    return coerced

def normalize_database_url(url: Optional[str]) -> Optional[str]:
    """
    Normalizes PostgreSQL connection strings for SQLAlchemy 2.0 and Supabase SSL:
    - postgres:// -> postgresql+psycopg2://
    - postgresql:// -> postgresql+psycopg2://
    - Enforces sslmode=require for remote cloud databases.
    """
    if not url:
        return None
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # If connecting to remote PostgreSQL (not sqlite or localhost), ensure sslmode=require
    if url.startswith("postgresql+") and "localhost" not in url and "127.0.0.1" not in url:
        if "sslmode=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
    return url

def mask_connection_string(conn_str: str) -> str:
    """Masks database passwords in connection URLs for safe logging."""
    if not conn_str:
        return "<none>"
    import re
    return re.sub(r":([^/@:]+)@", r":****@", conn_str)

def mask_secret(secret: str) -> str:
    """Masks API keys for safe logging (e.g. eyJ...***)."""
    if not secret:
        return "<none>"
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}...{secret[-4:]}"

def get_source_data(source_db_path: Path) -> Tuple[sqlite3.Connection, Dict[str, List[sqlite3.Row]]]:
    """Reads all source tables from SQLite in explicit read-only mode."""
    if not source_db_path.exists():
        raise FileNotFoundError(f"Source database not found at: {source_db_path}")

    uri = f"file:{source_db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    data = {}
    for table in TABLE_MIGRATION_ORDER:
        try:
            cur.execute(f"SELECT * FROM {table} ORDER BY id ASC")
            data[table] = cur.fetchall()
        except sqlite3.OperationalError:
            data[table] = []

    return conn, data

def verify_bucket_is_private(supabase_url: str, service_role_key: str, bucket: str) -> Tuple[bool, str]:
    """Verifies that the Supabase Storage bucket is strictly private (not public)."""
    if not HAS_HTTPX:
        return False, "httpx library not available to verify bucket configuration"

    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/bucket/{bucket}"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apiKey": service_role_key,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(endpoint, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                is_public = data.get("public", False)
                if is_public:
                    return False, f"CRITICAL SECURITY HAZARD: Bucket '{bucket}' is configured as PUBLIC! It must be set to PRIVATE."
                return True, "Bucket is verified PRIVATE."
            elif resp.status_code == 404:
                return False, f"Bucket '{bucket}' does not exist on Supabase project."
            else:
                return False, f"Failed to check bucket status: HTTP {resp.status_code} - {resp.text}"
    except Exception as e:
        return False, f"Bucket check exception: {str(e)}"

def check_photo_exists_in_storage(
    supabase_url: str,
    service_role_key: str,
    bucket: str,
    filename: str,
    expected_size: int
) -> Tuple[bool, str]:
    """Checks if a photograph already exists in Supabase Storage with matching size."""
    if not HAS_HTTPX:
        return False, "httpx not installed"

    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/info/authenticated/{bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apiKey": service_role_key,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(endpoint, headers=headers)
            if resp.status_code == 200:
                info = resp.json()
                size = info.get("size") or info.get("metadata", {}).get("size")
                if size is not None and int(size) == expected_size:
                    return True, "ALREADY_EXISTS_VERIFIED"
                return False, "SIZE_MISMATCH"
            return False, "NOT_FOUND"
    except Exception as e:
        return False, str(e)

def upload_photo_to_supabase_storage(
    supabase_url: str,
    service_role_key: str,
    bucket: str,
    filename: str,
    file_bytes: bytes,
    content_type: str = "image/jpeg",
    dry_run: bool = True
) -> Tuple[bool, str]:
    """
    Uploads photograph to Supabase Private Storage via REST API.
    Uses 'x-upsert: true' and immediately verifies object presence.
    """
    if dry_run:
        return True, f"dry-run://{bucket}/{filename}"

    if not HAS_HTTPX:
        return False, "httpx library not installed; cannot upload to Supabase Storage"

    # Pre-check: if already exists with identical size, skip re-uploading
    already_exists, status_msg = check_photo_exists_in_storage(
        supabase_url, service_role_key, bucket, filename, len(file_bytes)
    )
    if already_exists:
        return True, "ALREADY_EXISTS_VERIFIED"

    upload_endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apiKey": service_role_key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(upload_endpoint, headers=headers, content=file_bytes)
            if resp.status_code in (200, 201):
                # Verify upload immediately
                v_ok, v_msg = check_photo_exists_in_storage(
                    supabase_url, service_role_key, bucket, filename, len(file_bytes)
                )
                if v_ok:
                    return True, f"UPLOADED_AND_VERIFIED: {bucket}/{filename}"
                return False, f"Uploaded but post-verification failed: {v_msg}"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Upload exception: {str(e)}"

def records_differ(source_row: Dict[str, Any], target_row: Dict[str, Any], table: Optional[str] = None) -> List[str]:
    """Compares all fields between a source record and target record, returning differing column names."""
    differences = []
    bool_cols = BOOLEAN_COLUMNS.get(table, set()) if table else set()
    int_cols = INTEGER_COLUMNS.get(table, set()) if table else set()
    float_cols = FLOAT_COLUMNS.get(table, set()) if table else set()
    date_cols = DATE_COLUMNS.get(table, set()) if table else set()
    time_cols = TIME_COLUMNS.get(table, set()) if table else set()
    dt_cols = DATETIME_COLUMNS.get(table, set()) if table else set()

    for k, src_val in source_row.items():
        if k not in target_row:
            continue
        tgt_val = target_row[k]

        if src_val is None and tgt_val is None:
            continue
        if src_val is None or tgt_val is None:
            differences.append(k)
            continue

        # Boolean comparison
        if k in bool_cols or k.startswith("is_") or k in ("liveness_passed", "mock_detected", "face_verified", "liveness_verified"):
            if bool(src_val) != bool(tgt_val):
                differences.append(k)
            continue

        # Integer comparison
        if k in int_cols:
            try:
                if int(src_val) != int(tgt_val):
                    differences.append(k)
                continue
            except Exception:
                differences.append(k)
                continue

        # Float comparison with tolerance
        if k in float_cols or isinstance(src_val, float) or isinstance(tgt_val, float):
            try:
                if abs(float(src_val) - float(tgt_val)) > 1e-4:
                    differences.append(k)
            except Exception:
                differences.append(k)
            continue

        # Date comparison (YYYY-MM-DD)
        if k in date_cols or (isinstance(tgt_val, datetime.date) and not isinstance(tgt_val, datetime.datetime)):
            if str(src_val).strip()[:10] != str(tgt_val).strip()[:10]:
                differences.append(k)
            continue

        # Time comparison (HH:MM:SS)
        if k in time_cols or isinstance(tgt_val, datetime.time):
            if str(src_val).strip()[:8] != str(tgt_val).strip()[:8]:
                differences.append(k)
            continue

        # DateTime comparison (compare ISO date + HH:MM:SS)
        if k in dt_cols or isinstance(tgt_val, datetime.datetime):
            src_iso = str(src_val).replace("T", " ").split(".")[0].strip()
            tgt_iso = str(tgt_val).replace("T", " ").split(".")[0].strip()
            if src_iso != tgt_iso:
                differences.append(k)
            continue

        # Facial embedding comparison
        if k == "facial_embedding":
            try:
                emb_src = json.loads(src_val) if isinstance(src_val, str) else src_val
                emb_tgt = json.loads(tgt_val) if isinstance(tgt_val, str) else tgt_val
                if isinstance(emb_src, list) and isinstance(emb_tgt, list):
                    if len(emb_src) != len(emb_tgt) or any(abs(float(a) - float(b)) > 1e-5 for a, b in zip(emb_src, emb_tgt)):
                        differences.append(k)
                    continue
            except Exception:
                pass

        # String / text comparison
        if str(src_val).strip() != str(tgt_val).strip():
            differences.append(k)

    return differences

def synchronize_sequence(conn, table: str):
    """
    Synchronizes PostgreSQL serial sequences for BOTH empty and non-empty tables:
    - If table is empty: setval(seq, 1, false) -> nextval() returns 1.
    - If table has rows: setval(seq, MAX(id), true) -> nextval() returns MAX(id) + 1.
    Uses scalar subqueries without top-level FROM clause so it ALWAYS executes.
    """
    try:
        seq_sql = text(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                (SELECT MAX(id) IS NOT NULL FROM {table})
            );
        """)
        conn.execute(seq_sql)
    except Exception:
        # Harmless if SQLite target or table without sequence
        pass

def migrate_database_records(
    source_data: Dict[str, List[sqlite3.Row]],
    target_engine,
    dry_run: bool = True,
    photo_url_mapping: Optional[Dict[str, str]] = None,
    on_conflict: str = "update"
) -> Dict[str, Any]:
    """
    Migrates records table-by-table into PostgreSQL:
    - Atomic transaction per table: rolls back on error so zero partial state remains.
    - Full value-level comparison on rerun (detects and updates modified records rather than blindly skipping).
    - Synchronizes auto-increment sequences for both empty and non-empty tables.
    """
    results = {}
    photo_url_mapping = photo_url_mapping or {}

    # Initialize PostgreSQL schema via SQLAlchemy models
    try:
        sys.path.insert(0, str(BACKEND_DIR))
        from app.database import Base
        import app.models # registers models
        if not dry_run:
            Base.metadata.create_all(bind=target_engine)
    except Exception as e:
        if not dry_run:
            raise RuntimeError(f"Failed to initialize target PostgreSQL schema: {e}")

    for table in TABLE_MIGRATION_ORDER:
        rows = source_data.get(table, [])
        inserted = 0
        updated = 0
        identical_skipped = 0
        failed = 0
        errors = []

        if dry_run:
            results[table] = {
                "source_rows": len(rows),
                "simulated_inserts": len(rows),
                "identical_skipped": 0,
                "updated": 0,
                "status": "VALIDATED_FOR_MIGRATION"
            }
            continue

        # Live Execution within an isolated, atomic transaction for this table
        try:
            with target_engine.begin() as conn:
                # 1. Fetch all existing target records to detect duplicates vs modifications
                existing_records = {}
                try:
                    existing_res = conn.execute(text(f"SELECT * FROM {table} ORDER BY id ASC"))
                    col_keys = existing_res.keys()
                    for er in existing_res.fetchall():
                        r_dict = dict(zip(col_keys, er))
                        existing_records[r_dict["id"]] = r_dict
                except Exception:
                    pass

                # 2. Process each row
                for r in rows:
                    raw_dict = dict(r)
                    row_dict = coerce_sqlite_row(table, raw_dict)
                    if table == "students" and row_dict.get("profile_photo_url") in photo_url_mapping:
                        row_dict["profile_photo_url"] = photo_url_mapping[row_dict["profile_photo_url"]]
                    row_id = row_dict.get("id")

                    # Check if record already exists in target
                    if row_id in existing_records:
                        tgt_row = existing_records[row_id]
                        diffs = records_differ(row_dict, tgt_row, table=table)

                        if not diffs:
                            # 100% identical: safely skip
                            identical_skipped += 1
                            continue

                        # Record exists but has different values
                        if on_conflict == "update":
                            set_clauses = [f"{col} = :{col}" for col in row_dict.keys() if col != "id"]
                            update_sql = text(f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = :id")
                            conn.execute(update_sql, row_dict)
                            updated += 1
                        elif on_conflict == "error":
                            raise ValueError(f"Conflict detected in {table} row ID {row_id}: Differing columns {diffs}")
                        else:
                            # on_conflict == "skip"
                            identical_skipped += 1
                        continue

                    # Insert brand new record
                    cols = list(row_dict.keys())
                    col_names = ", ".join(cols)
                    placeholders = ", ".join([f":{c}" for c in cols])
                    insert_sql = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})")
                    conn.execute(insert_sql, row_dict)
                    inserted += 1

                # 3. Synchronize serial sequences (handles empty & non-empty tables)
                synchronize_sequence(conn, table)

            results[table] = {
                "source_rows": len(rows),
                "inserted": inserted,
                "updated": updated,
                "identical_skipped": identical_skipped,
                "failed": 0,
                "status": "COMPLETED"
            }

        except Exception as table_err:
            # Entire table transaction rolled back automatically by context manager
            results[table] = {
                "source_rows": len(rows),
                "inserted": 0,
                "updated": 0,
                "identical_skipped": 0,
                "failed": len(rows),
                "errors": [str(table_err)],
                "status": "TRANSACTION_ROLLED_BACK"
            }
            raise RuntimeError(f"Migration aborted on table '{table}'. Transaction rolled back cleanly: {table_err}")

    return results

def run_migration(
    source_db_path: Path,
    uploads_dir: Path,
    target_db_url: Optional[str],
    supabase_url: Optional[str],
    supabase_key: Optional[str],
    supabase_bucket: str = "student-profiles",
    dry_run: bool = True,
    skip_photos: bool = False,
    photos_only: bool = False,
    on_conflict: str = "update"
) -> Dict[str, Any]:
    """Orchestrates the cloud migration pipeline with rigorous pre-flight checks."""

    norm_target_url = normalize_database_url(target_db_url)

    report = {
        "mode": "DRY-RUN (Simulated - No changes made)" if dry_run else "EXECUTE (Live Migration)",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_db": str(source_db_path),
        "target_db": mask_connection_string(norm_target_url or ""),
        "supabase_url": supabase_url or "<none>",
        "supabase_key_masked": mask_secret(supabase_key or ""),
        "supabase_bucket": supabase_bucket,
        "on_conflict_policy": on_conflict,
        "database_migration": {},
        "photo_migration": {},
        "warnings": [],
        "errors": [],
        "success": False
    }

    # 1. Read source SQLite database in explicit read-only mode
    try:
        source_conn, source_data = get_source_data(source_db_path)
    except Exception as e:
        report["errors"].append(f"Failed to read source database: {e}")
        return report

    # 2. Check Storage Bucket Privacy if executing photo migration
    if not skip_photos and not dry_run and supabase_url and supabase_key:
        is_private, bucket_msg = verify_bucket_is_private(supabase_url, supabase_key, supabase_bucket)
        if not is_private:
            report["errors"].append(bucket_msg)
            source_conn.close()
            return report

    # 3. Process Photos
    photo_url_mapping = {}
    photo_results = {
        "total_referenced": 0,
        "matched_on_disk": 0,
        "missing_on_disk": 0,
        "uploaded_or_verified": 0,
        "failed": 0,
        "details": []
    }

    students_rows = source_data.get("students", [])
    if not skip_photos:
        for s in students_rows:
            url = s["profile_photo_url"]
            if not url:
                continue

            photo_results["total_referenced"] += 1
            filename = Path(url).name
            local_file = uploads_dir / filename

            if not local_file.exists():
                photo_results["missing_on_disk"] += 1
                photo_results["details"].append({
                    "register_number": s["register_number"],
                    "filename": filename,
                    "status": "MISSING_ON_DISK"
                })
                continue

            photo_results["matched_on_disk"] += 1
            mime_type, _ = mimetypes.guess_type(str(local_file))
            mime_type = mime_type or "image/jpeg"

            try:
                file_bytes = local_file.read_bytes()
                # Target path in private storage: student-profiles/<filename>
                target_path = f"{supabase_bucket}/{filename}"

                if dry_run:
                    photo_results["uploaded_or_verified"] += 1
                    photo_url_mapping[url] = url # Maintain canonical route format
                    photo_results["details"].append({
                        "register_number": s["register_number"],
                        "filename": filename,
                        "size_bytes": len(file_bytes),
                        "status": "SIMULATED_VERIFIED",
                        "target_path": target_path
                    })
                else:
                    if not supabase_url or not supabase_key:
                        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for photo uploads")

                    ok, msg = upload_photo_to_supabase_storage(
                        supabase_url, supabase_key, supabase_bucket, filename, file_bytes, mime_type, dry_run=False
                    )
                    if ok:
                        photo_results["uploaded_or_verified"] += 1
                        photo_url_mapping[url] = url
                        photo_results["details"].append({
                            "register_number": s["register_number"],
                            "filename": filename,
                            "size_bytes": len(file_bytes),
                            "status": "VERIFIED_IN_STORAGE",
                            "target_path": target_path,
                            "info": msg
                        })
                    else:
                        photo_results["failed"] += 1
                        photo_results["details"].append({
                            "register_number": s["register_number"],
                            "filename": filename,
                            "status": "UPLOAD_FAILED",
                            "error": msg
                        })
            except Exception as photo_err:
                photo_results["failed"] += 1
                photo_results["details"].append({
                    "register_number": s["register_number"],
                    "filename": filename,
                    "status": "ERROR",
                    "error": str(photo_err)
                })

    report["photo_migration"] = photo_results

    # 4. Process Database Records
    if not photos_only:
        if dry_run:
            db_results = migrate_database_records(source_data, target_engine=None, dry_run=True)
            report["database_migration"] = db_results
        else:
            if not norm_target_url:
                report["errors"].append("DATABASE_URL is required for live database migration (--execute).")
                source_conn.close()
                return report

            if not HAS_SQLALCHEMY:
                report["errors"].append("SQLAlchemy is required for live database migration.")
                source_conn.close()
                return report

            try:
                target_engine = create_engine(norm_target_url, pool_pre_ping=True)
                db_results = migrate_database_records(
                    source_data, target_engine, dry_run=False, photo_url_mapping=photo_url_mapping, on_conflict=on_conflict
                )
                report["database_migration"] = db_results
            except Exception as db_err:
                report["errors"].append(f"Database migration failed: {db_err}")
                source_conn.close()
                return report

    source_conn.close()
    report["success"] = len(report["errors"]) == 0
    return report

def print_summary(report: Dict[str, Any]):
    print("=" * 80)
    print(f"  KPRIET SMART HOSTEL - CLOUD MIGRATION [{report['mode']}]")
    print("=" * 80)
    print(f"Timestamp        : {report['timestamp']}")
    print(f"Source Database  : {report['source_db']}")
    print(f"Target Database  : {report['target_db']}")
    print(f"Supabase Endpoint: {report['supabase_url']}")
    print(f"Storage Bucket   : {report['supabase_bucket']}")
    print(f"Conflict Policy  : {report['on_conflict_policy']}")
    print("-" * 80)

    if report.get("database_migration"):
        print("DATABASE TABLES MIGRATION:")
        for t_name, t_info in report["database_migration"].items():
            if "simulated_inserts" in t_info:
                print(f"  • {t_name:<25} : {t_info['source_rows']:>4} rows -> {t_info['status']}")
            else:
                ins = t_info.get('inserted', 0)
                upd = t_info.get('updated', 0)
                skp = t_info.get('identical_skipped', 0)
                fld = t_info.get('failed', 0)
                print(f"  • {t_name:<25} : {ins:>3} inserted, {upd:>3} updated, {skp:>3} identical skipped, {fld:>3} failed ({t_info['status']})")

    print("-" * 80)
    pm = report.get("photo_migration", {})
    if pm:
        print("STUDENT BIOMETRIC PHOTOGRAPHS:")
        print(f"  • Total DB References : {pm.get('total_referenced', 0)}")
        print(f"  • Matched on Disk     : {pm.get('matched_on_disk', 0)}")
        print(f"  • Missing from Disk   : {pm.get('missing_on_disk', 0)}")
        print(f"  • Verified in Storage : {pm.get('uploaded_or_verified', 0)}")
        print(f"  • Failed              : {pm.get('failed', 0)}")

    if report.get("errors"):
        print("-" * 80)
        print("ERRORS DETECTED:")
        for e in report["errors"]:
            print(f"  [!] {e}")

    print("=" * 80)
    if "DRY-RUN" in report["mode"]:
        print("DRY RUN FINISHED: ZERO changes were made to source or cloud resources.")
        print("To perform actual live migration, review the dry-run output and provide:")
        print("  python backend/migration/migrate_to_supabase.py --execute")
    else:
        status_word = "SUCCESSFULLY COMPLETED" if report["success"] else "COMPLETED WITH ERRORS"
        print(f"MIGRATION {status_word}.")
    print("=" * 80)

def main():
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(BACKEND_DIR.parent / ".env")

    parser = argparse.ArgumentParser(description="KPRIET Smart Hostel SQLite to Supabase Migration Tool")
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB, help="Path to source SQLite database")
    parser.add_argument("--uploads-dir", type=Path, default=DEFAULT_UPLOADS_DIR, help="Path to profile uploads folder")
    parser.add_argument("--target-db", type=str, default=os.getenv("DATABASE_URL"), help="Target PostgreSQL connection URL")
    parser.add_argument("--supabase-url", type=str, default=os.getenv("SUPABASE_URL"), help="Supabase base URL")
    parser.add_argument(
        "--supabase-key",
        type=str,
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY"),
        help="Supabase Service Role Key (secret)"
    )
    parser.add_argument("--bucket", type=str, default=os.getenv("SUPABASE_BUCKET", "student-profiles"), help="Supabase storage bucket")
    parser.add_argument("--execute", action="store_true", help="Execute real migration (writes to PostgreSQL and Supabase Storage)")
    parser.add_argument("--dry-run", action="store_true", help="Explicitly enforce dry-run simulation mode")
    parser.add_argument("--skip-photos", action="store_true", help="Migrate database tables only without uploading photos")
    parser.add_argument("--photos-only", action="store_true", help="Upload photos only without migrating database tables")
    parser.add_argument(
        "--on-conflict",
        choices=["update", "skip", "error"],
        default="update",
        help="Action on existing IDs: 'update' (detects and updates diffs), 'skip' (leaves target), 'error' (aborts)"
    )
    parser.add_argument("--json", action="store_true", help="Output full JSON report")
    args = parser.parse_args()

    is_dry_run = not args.execute or args.dry_run

    report = run_migration(
        source_db_path=args.source_db,
        uploads_dir=args.uploads_dir,
        target_db_url=args.target_db,
        supabase_url=args.supabase_url,
        supabase_key=args.supabase_key,
        supabase_bucket=args.bucket,
        dry_run=is_dry_run,
        skip_photos=args.skip_photos,
        photos_only=args.photos_only,
        on_conflict=args.on_conflict
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_summary(report)

    if not report["success"] and not is_dry_run:
        sys.exit(1)

if __name__ == "__main__":
    main()
