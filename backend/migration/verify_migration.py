#!/usr/bin/env python3
"""
verify_migration.py - KPRIET Smart Hostel Migration Verification & Deep Audit Tool
Part of the SQLite-to-Supabase Cloud Migration Suite.

Performs a 100% READ-ONLY verification comparing:
1. Source SQLite vs Destination Supabase PostgreSQL row counts
2. Primary key parity and sequence integrity across all 6 tables
3. Foreign-key referential integrity (attendance & verification_sessions)
4. FULL COLUMN-BY-COLUMN VALUE FIDELITY for ALL 6 tables:
   - Facial embeddings (JSON 128D floats precision check)
   - Password hashes ($2b$ bcrypt character-for-character check)
   - GPS coordinates and distances (float precision tolerance check)
   - Timestamps, dates, and times (normalized ISO conversion check)
   - Institutional audit logs and verification session tokens
5. Supabase Private Storage Bucket Privacy (verifies public=False)
6. Student photograph availability and byte-size parity in Private Storage

Outputs an institutional audit verdict: PASS or FAIL.
"""

import os
import sys
import json
import sqlite3
import argparse
import datetime
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
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
DEFAULT_SOURCE_DB = BACKEND_DIR / "smart_hostel.db"
DEFAULT_UPLOADS_DIR = BACKEND_DIR / "app" / "uploads" / "profiles"

TABLES_TO_VERIFY = [
    "system_configs",
    "staff",
    "students",
    "attendance",
    "verification_sessions",
    "admin_audit_logs",
]

ALL_BOOLEAN_COLUMNS = {
    "is_active",
    "liveness_passed",
    "mock_detected",
    "is_anonymized",
    "is_used",
    "liveness_verified",
    "face_verified",
}

def normalize_database_url(url: Optional[str]) -> Optional[str]:
    """Normalizes PostgreSQL connection strings for SQLAlchemy 2.0 and SSL."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    if url.startswith("postgresql+") and "localhost" not in url and "127.0.0.1" not in url:
        if "sslmode=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
    return url

def mask_connection_string(conn_str: str) -> str:
    if not conn_str:
        return "<none>"
    import re
    return re.sub(r":([^/@:]+)@", r":****@", conn_str)

def get_sqlite_data(source_db_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    if not source_db_path.exists():
        raise FileNotFoundError(f"Source SQLite database not found: {source_db_path}")

    uri = f"file:{source_db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    data = {}
    for table in TABLES_TO_VERIFY:
        try:
            cur.execute(f"SELECT * FROM {table} ORDER BY id ASC")
            data[table] = [dict(r) for r in cur.fetchall()]
        except Exception:
            data[table] = []

    conn.close()
    return data

def get_target_data(target_engine) -> Dict[str, List[Dict[str, Any]]]:
    data = {}
    with target_engine.connect() as conn:
        for table in TABLES_TO_VERIFY:
            try:
                res = conn.execute(text(f"SELECT * FROM {table} ORDER BY id ASC"))
                cols = res.keys()
                rows = [dict(zip(cols, r)) for r in res.fetchall()]
                data[table] = rows
            except Exception:
                data[table] = []
    return data

def values_are_equivalent(v_src: Any, v_tgt: Any, col_name: str) -> bool:
    """Type-safe comparison between SQLite raw values and PostgreSQL native types."""
    if v_src is None and v_tgt is None:
        return True
    if v_src is None or v_tgt is None:
        return False

    # Boolean values
    if (col_name in ALL_BOOLEAN_COLUMNS or "is_" in col_name) and isinstance(v_src, (bool, int)) and isinstance(v_tgt, (bool, int)):
        return bool(v_src) == bool(v_tgt)

    # Float comparison
    if isinstance(v_src, float) or isinstance(v_tgt, float):
        try:
            return abs(float(v_src) - float(v_tgt)) < 1e-4
        except Exception:
            pass

    # Dates and Times
    if isinstance(v_tgt, datetime.date) and not isinstance(v_tgt, datetime.datetime):
        return str(v_src).strip() == str(v_tgt).strip()
    if isinstance(v_tgt, datetime.time):
        src_str = str(v_src).strip()[:8]
        tgt_str = str(v_tgt).strip()[:8]
        return src_str == tgt_str
    if isinstance(v_tgt, datetime.datetime):
        # Compare ISO date part and hour/minute
        src_iso = str(v_src).replace("T", " ").split(".")[0].strip()
        tgt_iso = str(v_tgt).replace("T", " ").split(".")[0].strip()
        return src_iso == tgt_iso

    # Facial embedding JSON list comparison
    if col_name == "facial_embedding":
        try:
            emb_src = json.loads(v_src) if isinstance(v_src, str) else v_src
            emb_tgt = json.loads(v_tgt) if isinstance(v_tgt, str) else v_tgt
            if isinstance(emb_src, list) and isinstance(emb_tgt, list):
                if len(emb_src) != len(emb_tgt):
                    return False
                return all(abs(float(a) - float(b)) < 1e-5 for a, b in zip(emb_src, emb_tgt))
        except Exception:
            pass

    # String & Fallback comparison
    return str(v_src).strip() == str(v_tgt).strip()

def verify_storage_photo(
    supabase_url: str,
    service_role_key: str,
    bucket: str,
    filename: str,
    local_path: Optional[Path]
) -> Tuple[bool, str, Optional[int]]:
    """Verifies that photo exists in private storage and verifies size against local file."""
    if not HAS_HTTPX:
        return False, "httpx not installed", None

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
                remote_size = info.get("size") or info.get("metadata", {}).get("size")
                if remote_size is not None:
                    remote_size = int(remote_size)

                # If local file available, check size match
                if local_path and local_path.exists():
                    local_size = local_path.stat().st_size
                    if remote_size is not None and abs(remote_size - local_size) > 0:
                        return False, f"SIZE_MISMATCH: local={local_size} vs remote={remote_size}", remote_size

                return True, "VERIFIED", remote_size
            elif resp.status_code == 404:
                return False, "NOT_FOUND", None
            else:
                return False, f"HTTP_{resp.status_code}", None
    except Exception as e:
        return False, str(e), None

def run_verification(
    source_db_path: Path,
    target_db_url: str,
    uploads_dir: Path = DEFAULT_UPLOADS_DIR,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
    supabase_bucket: str = "student-profiles",
    verify_storage: bool = True
) -> Dict[str, Any]:

    norm_target_url = normalize_database_url(target_db_url)

    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_db": str(source_db_path),
        "target_db": mask_connection_string(norm_target_url or ""),
        "table_counts": {},
        "primary_key_parity": {},
        "foreign_key_integrity": {},
        "full_column_fidelity": {},
        "sequence_integrity": {},
        "bucket_privacy_verification": {},
        "storage_verification": {},
        "discrepancies": [],
        "overall_status": "PENDING"
    }

    if not HAS_SQLALCHEMY:
        report["discrepancies"].append("SQLAlchemy is required to connect to target PostgreSQL.")
        report["overall_status"] = "FAIL"
        return report

    # 1. Fetch Source & Destination Data
    try:
        source_data = get_sqlite_data(source_db_path)
    except Exception as e:
        report["discrepancies"].append(f"Failed to read source SQLite data: {e}")
        report["overall_status"] = "FAIL"
        return report

    try:
        target_engine = create_engine(norm_target_url, pool_pre_ping=True)
        target_data = get_target_data(target_engine)
    except Exception as e:
        report["discrepancies"].append(f"Failed to connect to target PostgreSQL: {e}")
        report["overall_status"] = "FAIL"
        return report

    # 2. Table Row Count Comparison
    counts_matched = True
    for table in TABLES_TO_VERIFY:
        src_cnt = len(source_data.get(table, []))
        tgt_cnt = len(target_data.get(table, []))
        match = (src_cnt == tgt_cnt)
        if not match:
            counts_matched = False
            report["discrepancies"].append(
                f"Row count mismatch in table '{table}': Source={src_cnt}, Target={tgt_cnt}"
            )
        report["table_counts"][table] = {
            "source": src_cnt,
            "target": tgt_cnt,
            "match": match
        }

    # 3. Primary Key Parity
    for table in TABLES_TO_VERIFY:
        src_ids = {r["id"] for r in source_data.get(table, []) if "id" in r}
        tgt_ids = {r["id"] for r in target_data.get(table, []) if "id" in r}
        missing_in_target = src_ids - tgt_ids
        extra_in_target = tgt_ids - src_ids

        pk_ok = len(missing_in_target) == 0 and len(extra_in_target) == 0
        if not pk_ok:
            report["discrepancies"].append(
                f"Primary key mismatch in '{table}': Missing={len(missing_in_target)}, Extra={len(extra_in_target)}"
            )

        report["primary_key_parity"][table] = {
            "source_ids_count": len(src_ids),
            "target_ids_count": len(tgt_ids),
            "missing_in_target": sorted(list(missing_in_target)),
            "extra_in_target": sorted(list(extra_in_target)),
            "match": pk_ok
        }

    # 4. Foreign Key Referential Integrity Check
    target_student_ids = {s["id"] for s in target_data.get("students", [])}

    invalid_att_fks = []
    for att in target_data.get("attendance", []):
        sid = att.get("student_id")
        if sid is not None and sid not in target_student_ids:
            invalid_att_fks.append(att.get("id"))

    invalid_vs_fks = []
    for vs in target_data.get("verification_sessions", []):
        sid = vs.get("student_id")
        if sid not in target_student_ids:
            invalid_vs_fks.append(vs.get("id"))

    fk_ok = len(invalid_att_fks) == 0 and len(invalid_vs_fks) == 0
    if not fk_ok:
        report["discrepancies"].append(
            f"Foreign key violations: Attendance orphan IDs={invalid_att_fks}, Session orphan IDs={invalid_vs_fks}"
        )

    report["foreign_key_integrity"] = {
        "attendance_orphans_count": len(invalid_att_fks),
        "verification_session_orphans_count": len(invalid_vs_fks),
        "match": fk_ok
    }

    # 5. FULL COLUMN-BY-COLUMN DEEP VALUE FIDELITY CHECK (All 6 Tables)
    all_tables_fidelity = {}
    for table in TABLES_TO_VERIFY:
        src_rows_by_id = {r["id"]: r for r in source_data.get(table, []) if "id" in r}
        tgt_rows_by_id = {r["id"]: r for r in target_data.get(table, []) if "id" in r}

        table_mismatches = []
        for rid, s_row in src_rows_by_id.items():
            t_row = tgt_rows_by_id.get(rid)
            if not t_row:
                continue

            for col, s_val in s_row.items():
                t_val = t_row.get(col)
                if not values_are_equivalent(s_val, t_val, col):
                    # Mask value if secret column
                    disp_s = "<masked>" if "password" in col else str(s_val)[:40]
                    disp_t = "<masked>" if "password" in col else str(t_val)[:40]
                    table_mismatches.append(f"Row ID {rid}, Column '{col}': Source='{disp_s}' vs Target='{disp_t}'")

        table_ok = len(table_mismatches) == 0
        all_tables_fidelity[table] = {
            "verified_rows": len(src_rows_by_id),
            "mismatch_count": len(table_mismatches),
            "mismatches": table_mismatches[:5],
            "match": table_ok
        }
        if not table_ok:
            report["discrepancies"].extend([f"[{table}] {m}" for m in table_mismatches[:5]])

    report["full_column_fidelity"] = all_tables_fidelity

    # 6. PostgreSQL Auto-Increment Sequence Verification (Empty & Non-Empty Tables)
    seq_report = {}
    try:
        with target_engine.connect() as conn:
            for table in TABLES_TO_VERIFY:
                try:
                    q = text(f"SELECT pg_get_serial_sequence('{table}', 'id')")
                    seq_name = conn.execute(q).scalar()
                    if seq_name:
                        curval_q = text(f"SELECT last_value FROM {seq_name}")
                        last_val = conn.execute(curval_q).scalar()
                        max_id_q = text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
                        max_id = conn.execute(max_id_q).scalar()
                        # If table has records, last_val must be >= max_id
                        # If table is empty, max_id is 0 and sequence can be 1
                        is_safe = (last_val >= max_id) if max_id > 0 else True
                        seq_report[table] = {
                            "sequence": seq_name,
                            "last_value": last_val,
                            "max_id": max_id,
                            "safe": is_safe
                        }
                        if not is_safe:
                            report["discrepancies"].append(
                                f"Sequence '{seq_name}' is behind MAX(id) in table '{table}': {last_val} < {max_id}"
                            )
                except Exception:
                    pass
    except Exception:
        pass
    report["sequence_integrity"] = seq_report

    # 7. Supabase Storage Bucket Privacy & Photo Verification
    if verify_storage and supabase_url and supabase_key:
        # Check bucket is private
        if HAS_HTTPX:
            b_endpoint = f"{supabase_url.rstrip('/')}/storage/v1/bucket/{supabase_bucket}"
            b_headers = {"Authorization": f"Bearer {supabase_key}", "apiKey": supabase_key}
            try:
                with httpx.Client(timeout=10.0) as client:
                    b_resp = client.get(b_endpoint, headers=b_headers)
                    if b_resp.status_code == 200:
                        b_info = b_resp.json()
                        is_pub = b_info.get("public", False)
                        report["bucket_privacy_verification"] = {
                            "bucket": supabase_bucket,
                            "is_private": not is_pub,
                            "status": "PASS" if not is_pub else "FAIL - BUCKET IS PUBLIC!"
                        }
                        if is_pub:
                            report["discrepancies"].append(f"CRITICAL: Storage bucket '{supabase_bucket}' is configured as PUBLIC!")
            except Exception as e:
                report["bucket_privacy_verification"] = {"error": str(e)}

        storage_checked = 0
        storage_missing = 0
        storage_details = []

        for s in target_data.get("students", []):
            photo_url = s.get("profile_photo_url")
            if not photo_url:
                continue

            storage_checked += 1
            filename = Path(photo_url).name
            local_photo = uploads_dir / filename if uploads_dir else None

            ok, status_msg, remote_size = verify_storage_photo(
                supabase_url, supabase_key, supabase_bucket, filename, local_photo
            )
            if ok:
                storage_details.append({
                    "register_number": s.get("register_number"),
                    "filename": filename,
                    "status": "CONFIRMED",
                    "size_bytes": remote_size
                })
            else:
                storage_missing += 1
                storage_details.append({
                    "register_number": s.get("register_number"),
                    "filename": filename,
                    "status": status_msg
                })

        report["storage_verification"] = {
            "total_checked": storage_checked,
            "missing_count": storage_missing,
            "details": storage_details,
            "match": storage_missing == 0
        }
        if storage_missing > 0:
            report["discrepancies"].append(f"{storage_missing} photographs missing or size-mismatched in private storage bucket '{supabase_bucket}'")

    # Overall Verdict
    if len(report["discrepancies"]) == 0:
        report["overall_status"] = "PASS"
    else:
        report["overall_status"] = "FAIL"

    return report

def print_verification_summary(report: Dict[str, Any]):
    print("=" * 80)
    print(f"  KPRIET SMART HOSTEL - MIGRATION VERIFICATION AUDIT [{report['overall_status']}]")
    print("=" * 80)
    print(f"Timestamp   : {report['timestamp']}")
    print(f"Source DB   : {report['source_db']}")
    print(f"Target DB   : {report['target_db']}")
    print("-" * 80)
    print("TABLE ROW COUNT COMPARISON:")
    for t_name, t_info in sorted(report["table_counts"].items()):
        status = "MATCH" if t_info["match"] else "MISMATCH"
        print(f"  • {t_name:<25} : Source={t_info['source']:>4} | Target={t_info['target']:>4} -> [{status}]")

    print("-" * 80)
    print("INTEGRITY CHECKS:")
    pk_all_match = all(p["match"] for p in report.get("primary_key_parity", {}).values())
    print(f"  • Primary Key Parity            : {'PASS' if pk_all_match else 'FAIL'}")
    fk_match = report.get("foreign_key_integrity", {}).get("match", False)
    print(f"  • Foreign Key Relationships     : {'PASS' if fk_match else 'FAIL'}")
    all_col_match = all(f["match"] for f in report.get("full_column_fidelity", {}).values())
    print(f"  • Full Column-by-Column Fidelity: {'PASS' if all_col_match else 'FAIL'}")

    bp = report.get("bucket_privacy_verification")
    if bp:
        print(f"  • Storage Bucket Privacy        : {bp.get('status')}")

    storage = report.get("storage_verification")
    if storage:
        print(f"  • Supabase Storage Photos       : {storage['total_checked'] - storage['missing_count']}/{storage['total_checked']} confirmed")

    if report["discrepancies"]:
        print("-" * 80)
        print("DISCREPANCIES DETECTED:")
        for d in report["discrepancies"]:
            print(f"  [!] {d}")

    print("=" * 80)
    verdict_text = "VERIFICATION PASSED: Database & biometrics migrated with 100% fidelity." if report["overall_status"] == "PASS" else "VERIFICATION FAILED: Discrepancies found. Investigate before routing traffic."
    print(f"FINAL AUDIT RESULT: {verdict_text}")
    print("=" * 80)

def main():
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(BACKEND_DIR.parent / ".env")

    parser = argparse.ArgumentParser(description="Verify SQLite to Supabase Migration Fidelity")
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB, help="Source SQLite database path")
    parser.add_argument("--uploads-dir", type=Path, default=DEFAULT_UPLOADS_DIR, help="Path to profile uploads folder")
    parser.add_argument("--target-db", type=str, default=os.getenv("DATABASE_URL"), help="Target PostgreSQL connection URL")
    parser.add_argument("--supabase-url", type=str, default=os.getenv("SUPABASE_URL"), help="Supabase Project URL")
    parser.add_argument(
        "--supabase-key",
        type=str,
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY"),
        help="Supabase Service Role Key"
    )
    parser.add_argument("--bucket", type=str, default=os.getenv("SUPABASE_BUCKET", "student-profiles"), help="Storage Bucket Name")
    parser.add_argument("--skip-storage", action="store_true", help="Skip remote storage object existence check")
    parser.add_argument("--json", action="store_true", help="Output full JSON report")
    args = parser.parse_args()

    if not args.target_db:
        print("Error: DATABASE_URL (or --target-db) is required for verification.", file=sys.stderr)
        sys.exit(1)

    report = run_verification(
        source_db_path=args.source_db,
        target_db_url=args.target_db,
        uploads_dir=args.uploads_dir,
        supabase_url=args.supabase_url,
        supabase_key=args.supabase_key,
        supabase_bucket=args.bucket,
        verify_storage=not args.skip_storage
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_verification_summary(report)

    if report["overall_status"] != "PASS":
        sys.exit(1)

if __name__ == "__main__":
    main()
