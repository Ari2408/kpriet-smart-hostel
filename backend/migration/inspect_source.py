#!/usr/bin/env python3
"""
inspect_source.py - KPRIET Smart Hostel SQLite Source Database & Asset Inspector
Part of the SQLite-to-Supabase Cloud Migration Suite.

Performs a 100% READ-ONLY inspection of:
- SQLite tables, row counts, and schema definitions
- Primary keys, foreign keys, indexes, and constraints
- Student facial embeddings and password hash integrity
- Student profile photographs on disk and database reference mapping
"""

import os
import sys
import json
import sqlite3
from pathlib import Path

# Base paths
MIGRATION_DIR = Path(__file__).resolve().parent
BACKEND_DIR = MIGRATION_DIR.parent
DEFAULT_DB_PATH = BACKEND_DIR / "smart_hostel.db"
DEFAULT_UPLOADS_DIR = BACKEND_DIR / "app" / "uploads" / "profiles"

EXPECTED_TABLES = [
    "system_configs",
    "staff",
    "students",
    "attendance",
    "verification_sessions",
    "admin_audit_logs",
]

def get_readonly_connection(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")
    # Open SQLite in explicit read-only URI mode to guarantee zero data alteration
    uri_path = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri_path, uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def inspect_database(db_path: Path, uploads_dir: Path) -> dict:
    conn = get_readonly_connection(db_path)
    cur = conn.cursor()

    report = {
        "database_path": str(db_path),
        "database_size_bytes": db_path.stat().st_size,
        "uploads_dir": str(uploads_dir),
        "tables": {},
        "missing_expected_tables": [],
        "extra_tables": [],
        "foreign_keys": {},
        "indexes": {},
        "photo_inventory": {},
        "biometrics_integrity": {},
        "passwords_integrity": {},
    }

    # 1. Discover all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    existing_tables = sorted([r[0] for r in cur.fetchall()])
    
    for expected in EXPECTED_TABLES:
        if expected not in existing_tables:
            report["missing_expected_tables"].append(expected)
    for existing in existing_tables:
        if existing not in EXPECTED_TABLES:
            report["extra_tables"].append(existing)

    # 2. Inspect table row counts and schema
    for table in existing_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]

        cur.execute(f"PRAGMA table_info({table})")
        columns = []
        for col in cur.fetchall():
            columns.append({
                "cid": col["cid"],
                "name": col["name"],
                "type": col["type"],
                "notnull": bool(col["notnull"]),
                "default_value": col["dflt_value"],
                "is_primary_key": bool(col["pk"]),
            })

        cur.execute(f"PRAGMA foreign_key_list({table})")
        fks = []
        for fk in cur.fetchall():
            fks.append({
                "id": fk["id"],
                "seq": fk["seq"],
                "target_table": fk["table"],
                "from_column": fk["from"],
                "to_column": fk["to"],
                "on_update": fk["on_update"],
                "on_delete": fk["on_delete"],
            })

        cur.execute(f"PRAGMA index_list({table})")
        indexes = []
        for idx in cur.fetchall():
            indexes.append({
                "name": idx["name"],
                "unique": bool(idx["unique"]),
                "origin": idx["origin"],
            })

        report["tables"][table] = {
            "row_count": count,
            "columns": columns,
            "foreign_keys": fks,
            "indexes": indexes,
        }

    # 3. Biometrics & Passwords integrity check
    if "students" in existing_tables:
        cur.execute("SELECT id, register_number, password_hash, facial_embedding, profile_photo_url FROM students")
        students = cur.fetchall()

        valid_embeddings = 0
        invalid_embeddings = 0
        valid_bcrypt = 0
        invalid_bcrypt = 0
        photo_refs = []

        for s in students:
            # Check bcrypt hash format ($2a$ or $2b$)
            pw = s["password_hash"] or ""
            if pw.startswith("$2a$") or pw.startswith("$2b$"):
                valid_bcrypt += 1
            else:
                invalid_bcrypt += 1

            # Check facial embedding JSON format & dimensions
            emb_raw = s["facial_embedding"] or ""
            try:
                emb_list = json.loads(emb_raw)
                if isinstance(emb_list, list) and len(emb_list) == 128:
                    valid_embeddings += 1
                else:
                    invalid_embeddings += 1
            except Exception:
                invalid_embeddings += 1

            photo_refs.append({
                "student_id": s["id"],
                "register_number": s["register_number"],
                "profile_photo_url": s["profile_photo_url"],
            })

        report["biometrics_integrity"] = {
            "total_students": len(students),
            "valid_128d_embeddings": valid_embeddings,
            "invalid_embeddings": invalid_embeddings,
        }
        report["passwords_integrity"] = {
            "total_students": len(students),
            "valid_bcrypt_hashes": valid_bcrypt,
            "invalid_bcrypt_hashes": invalid_bcrypt,
        }

        # 4. Photo files inventory
        disk_files = {}
        if uploads_dir.exists():
            for p in uploads_dir.iterdir():
                if p.is_file() and p.name != ".gitkeep":
                    disk_files[p.name] = {
                        "size_bytes": p.stat().st_size,
                        "suffix": p.suffix.lower(),
                    }

        referenced_files = set()
        missing_photos = []
        matched_photos = []

        for ref in photo_refs:
            url = ref["profile_photo_url"]
            if not url:
                missing_photos.append({
                    "student_id": ref["student_id"],
                    "register_number": ref["register_number"],
                    "reason": "NULL_OR_EMPTY_URL",
                })
                continue

            fname = Path(url).name
            referenced_files.add(fname)
            if fname in disk_files:
                matched_photos.append({
                    "student_id": ref["student_id"],
                    "register_number": ref["register_number"],
                    "filename": fname,
                    "size_bytes": disk_files[fname]["size_bytes"],
                })
            else:
                missing_photos.append({
                    "student_id": ref["student_id"],
                    "register_number": ref["register_number"],
                    "filename": fname,
                    "reason": "FILE_NOT_FOUND_ON_DISK",
                })

        unreferenced_disk_files = sorted(list(set(disk_files.keys()) - referenced_files))

        report["photo_inventory"] = {
            "total_disk_files": len(disk_files),
            "referenced_in_db": len(referenced_files),
            "matched_on_disk": len(matched_photos),
            "missing_on_disk": missing_photos,
            "unreferenced_on_disk": unreferenced_disk_files,
        }

    conn.close()
    return report

def print_text_summary(report: dict):
    print("=" * 80)
    print("  KPRIET SMART HOSTEL - SOURCE DATABASE & ASSET INSPECTION REPORT")
    print("=" * 80)
    print(f"Database Path : {report['database_path']}")
    print(f"Database Size : {report['database_size_bytes']:,} bytes ({report['database_size_bytes']/1024:.2f} KB)")
    print(f"Uploads Dir   : {report['uploads_dir']}")
    print("-" * 80)
    print("TABLES & ROW COUNTS:")
    for t_name, t_data in sorted(report["tables"].items()):
        col_count = len(t_data["columns"])
        fk_count = len(t_data["foreign_keys"])
        print(f"  • {t_name:<25} : {t_data['row_count']:>5} rows  ({col_count} columns, {fk_count} FKs)")

    if report["missing_expected_tables"]:
        print(f"  [!] Missing expected tables: {report['missing_expected_tables']}")
    if report["extra_tables"]:
        print(f"  [*] Extra tables discovered : {report['extra_tables']}")

    print("-" * 80)
    biom = report.get("biometrics_integrity", {})
    pw = report.get("passwords_integrity", {})
    print("BIOMETRICS & CREDENTIALS INTEGRITY:")
    print(f"  • Total Students       : {biom.get('total_students', 0)}")
    print(f"  • 128D Embeddings Valid: {biom.get('valid_128d_embeddings', 0)} / {biom.get('total_students', 0)}")
    print(f"  • Bcrypt Hashes Valid  : {pw.get('valid_bcrypt_hashes', 0)} / {pw.get('total_students', 0)}")

    print("-" * 80)
    photos = report.get("photo_inventory", {})
    print("STUDENT PROFILE PHOTOGRAPHS INVENTORY:")
    print(f"  • Photos Stored on Disk    : {photos.get('total_disk_files', 0)}")
    print(f"  • Photos Referenced in DB  : {photos.get('referenced_in_db', 0)}")
    print(f"  • Successfully Matched     : {photos.get('matched_on_disk', 0)}")
    print(f"  • Missing from Disk        : {len(photos.get('missing_on_disk', []))}")
    print(f"  • Unreferenced on Disk     : {len(photos.get('unreferenced_on_disk', []))}")

    if photos.get("missing_on_disk"):
        print("  [!] Missing Photograph Details:")
        for m in photos["missing_on_disk"]:
            print(f"      - RegNo: {m['register_number']}, File: {m.get('filename', m.get('reason'))}")

    if photos.get("unreferenced_on_disk"):
        print(f"  [*] Unreferenced files ({len(photos['unreferenced_on_disk'])}):")
        for u in photos["unreferenced_on_disk"][:5]:
            print(f"      - {u}")
        if len(photos["unreferenced_on_disk"]) > 5:
            print(f"      ... and {len(photos['unreferenced_on_disk']) - 5} more")

    print("=" * 80)
    print("Inspection complete. 100% Read-Only mode. No changes were made to the source data.")
    print("=" * 80)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Inspect KPRIET Smart Hostel SQLite Database and Assets")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--uploads", type=Path, default=DEFAULT_UPLOADS_DIR, help="Path to uploads directory")
    parser.add_argument("--json", action="store_true", help="Output full JSON report")
    args = parser.parse_args()

    try:
        report = inspect_database(args.db, args.uploads)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_text_summary(report)
    except Exception as e:
        print(f"Error during inspection: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
