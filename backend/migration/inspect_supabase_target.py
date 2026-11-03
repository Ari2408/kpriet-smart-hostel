#!/usr/bin/env python3
"""
inspect_supabase_target.py - Read-Only Supabase Target Database Inspection Tool
Part of the KPRIET Smart Hostel Cloud Migration Suite.

Performs 100% READ-ONLY inspection of the target PostgreSQL database:
1. Loads and normalizes DATABASE_URL from backend/.env (enforcing SSL).
2. Connects using SQLAlchemy and queries PostgreSQL metadata catalogs.
3. Discovers all existing public tables, columns, primary keys, foreign keys, and indexes.
4. Audits the six application tables:
   - system_configs
   - staff
   - students
   - attendance
   - verification_sessions
   - admin_audit_logs
5. Reports row counts for existing tables (without reading PII or sensitive data).
6. Identifies unexpected tables or existing rows that could conflict with migration.
7. Evaluates whether the target database is clean and suitable for migration.

SAFETY GUARANTEES:
- Strictly executes read-only queries (SELECT).
- Zero table creation, alteration, deletion, or truncation.
- Zero inspection or logging of student names, emails, passwords, embeddings, or attendance data.
- Database passwords and connection strings are masked in all console outputs.
- Safely closes database connections and engine pools.
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from dotenv import load_dotenv

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

EXPECTED_APPLICATION_TABLES = [
    "system_configs",
    "staff",
    "students",
    "attendance",
    "verification_sessions",
    "admin_audit_logs",
]

def mask_connection_string(conn_str: str) -> str:
    """Masks database passwords in connection URLs for safe display."""
    if not conn_str:
        return "<not set>"
    return re.sub(r":([^/@:]+)@", r":****@", conn_str)

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

    if url.startswith("postgresql+") and "localhost" not in url and "127.0.0.1" not in url:
        if "sslmode=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
    return url

def load_target_url(env_file_path: Path, override_url: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Loads and normalizes DATABASE_URL from .env or override parameter."""
    if override_url:
        return normalize_database_url(override_url), "Command-line override"

    if env_file_path.exists():
        load_dotenv(env_file_path)
        source_label = str(env_file_path)
    elif FALLBACK_ENV_FILE.exists():
        load_dotenv(FALLBACK_ENV_FILE)
        source_label = str(FALLBACK_ENV_FILE)
    else:
        load_dotenv()
        source_label = "<environment>"

    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        return None, f"DATABASE_URL not set in {source_label}"
    if "sqlite" in raw_url.lower():
        return None, f"DATABASE_URL in {source_label} points to SQLite. Must point to Supabase PostgreSQL."

    return normalize_database_url(raw_url), source_label

def inspect_target_database(target_url: str) -> Dict[str, Any]:
    """
    Connects to PostgreSQL in read-only mode and inspects:
    - Tables in 'public' schema
    - Application table presence & row counts (using SELECT COUNT(*))
    - Columns, PKs, FKs, Indexes, and Constraints
    - Potential schema/data conflicts
    """
    report = {
        "status": "PENDING",
        "database_url_masked": mask_connection_string(target_url),
        "all_public_tables": [],
        "expected_tables_found": [],
        "expected_tables_missing": [],
        "unexpected_tables": [],
        "application_table_stats": {},
        "schema_details": {},
        "target_is_empty": True,
        "is_suitable_for_migration": False,
        "suitability_assessment": "",
        "warnings": [],
        "errors": [],
    }

    if not HAS_SQLALCHEMY:
        report["status"] = "FAIL"
        report["errors"].append("SQLAlchemy is not installed in the current Python environment. Run: pip install sqlalchemy")
        return report

    try:
        engine = create_engine(
            target_url,
            connect_args={"connect_timeout": 10},
            pool_pre_ping=True
        )

        with engine.connect() as conn:
            # 1. Inspect all tables in public schema
            tables_query = text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            public_tables = [r[0] for r in conn.execute(tables_query).fetchall()]
            report["all_public_tables"] = public_tables

            # Categorize tables
            for exp in EXPECTED_APPLICATION_TABLES:
                if exp in public_tables:
                    report["expected_tables_found"].append(exp)
                else:
                    report["expected_tables_missing"].append(exp)

            for existing in public_tables:
                if existing not in EXPECTED_APPLICATION_TABLES:
                    report["unexpected_tables"].append(existing)

            # 2. Row counts for application tables (Safe SELECT COUNT(*) only)
            total_app_rows = 0
            for exp in report["expected_tables_found"]:
                count_query = text(f'SELECT COUNT(*) FROM "{exp}";')
                row_count = conn.execute(count_query).scalar() or 0
                report["application_table_stats"][exp] = {
                    "exists": True,
                    "row_count": row_count
                }
                if row_count > 0:
                    total_app_rows += row_count
                    report["target_is_empty"] = False

            for missing in report["expected_tables_missing"]:
                report["application_table_stats"][missing] = {
                    "exists": False,
                    "row_count": 0
                }

            # 3. Columns inspection
            cols_query = text("""
                SELECT table_name, column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
            """)
            cols_res = conn.execute(cols_query).fetchall()
            columns_by_table: Dict[str, List[Dict[str, Any]]] = {}
            for r in cols_res:
                t_name = r[0]
                if t_name not in columns_by_table:
                    columns_by_table[t_name] = []
                columns_by_table[t_name].append({
                    "column_name": r[1],
                    "data_type": r[2],
                    "is_nullable": r[3] == "YES",
                    "default": r[4]
                })

            # 4. Primary keys inspection
            pk_query = text("""
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
                ORDER BY tc.table_name, kcu.ordinal_position;
            """)
            pk_res = conn.execute(pk_query).fetchall()
            pk_by_table: Dict[str, List[str]] = {}
            for r in pk_res:
                pk_by_table.setdefault(r[0], []).append(r[1])

            # 5. Foreign keys inspection
            fk_query = text("""
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name,
                    rc.delete_rule,
                    rc.update_rule
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.referential_constraints AS rc
                  ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public';
            """)
            fk_res = conn.execute(fk_query).fetchall()
            fk_by_table: Dict[str, List[Dict[str, Any]]] = {}
            for r in fk_res:
                fk_by_table.setdefault(r[0], []).append({
                    "column": r[1],
                    "foreign_table": r[2],
                    "foreign_column": r[3],
                    "delete_rule": r[4],
                    "update_rule": r[5]
                })

            # 6. Indexes inspection
            idx_query = text("""
                SELECT tablename, indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname;
            """)
            idx_res = conn.execute(idx_query).fetchall()
            idx_by_table: Dict[str, List[Dict[str, Any]]] = {}
            for r in idx_res:
                idx_by_table.setdefault(r[0], []).append({
                    "index_name": r[1],
                    "definition": r[2]
                })

            # Assemble schema details
            for t_name in public_tables:
                report["schema_details"][t_name] = {
                    "columns": columns_by_table.get(t_name, []),
                    "primary_key": pk_by_table.get(t_name, []),
                    "foreign_keys": fk_by_table.get(t_name, []),
                    "indexes": idx_by_table.get(t_name, [])
                }

        engine.dispose()
        report["status"] = "PASS"

        # 7. Evaluate Suitability Assessment
        if len(public_tables) == 0:
            report["is_suitable_for_migration"] = True
            report["target_is_empty"] = True
            report["suitability_assessment"] = "PRISTINE EMPTY TARGET: Zero public tables exist. Clean environment ready for initial migration."
        elif len(report["expected_tables_found"]) == len(EXPECTED_APPLICATION_TABLES) and total_app_rows == 0 and len(report["unexpected_tables"]) == 0:
            report["is_suitable_for_migration"] = True
            report["target_is_empty"] = True
            report["suitability_assessment"] = "PRE-INITIALIZED CLEAN SCHEMA: All 6 application tables exist with 0 rows. Perfect state for fresh migration."
        elif total_app_rows > 0:
            report["is_suitable_for_migration"] = True # Idempotent migration tool supports updates
            report["target_is_empty"] = False
            report["suitability_assessment"] = f"EXISTING DATA DETECTED ({total_app_rows} total rows across application tables). The migration script can be run with --on-conflict update to update or synchronize records safely."
            report["warnings"].append(f"Target database already contains {total_app_rows} application records.")
        elif len(report["unexpected_tables"]) > 0:
            report["is_suitable_for_migration"] = True
            report["suitability_assessment"] = f"NON-EMPTY TARGET: {len(report['unexpected_tables'])} other table(s) exist in public schema ({', '.join(report['unexpected_tables'])}). Verify these tables do not collide with hostel entities."
            report["warnings"].append(f"Unexpected tables found: {report['unexpected_tables']}")

    except Exception as e:
        report["status"] = "FAIL"
        safe_err = mask_connection_string(str(e))
        if "No module named 'psycopg2'" in safe_err:
            report["errors"].append("PostgreSQL driver 'psycopg2' not found. Run: pip install psycopg2-binary")
        else:
            report["errors"].append(f"Connection/Query error: {safe_err}")

    return report

def print_inspection_report(report: Dict[str, Any]):
    print("=" * 80)
    print("  KPRIET SMART HOSTEL - SUPABASE TARGET DATABASE INSPECTION (READ-ONLY)")
    print("=" * 80)
    print(f"Connection Status : [{report['status']}]")
    print(f"Target Database   : {report['database_url_masked']}")
    print("-" * 80)

    if report["status"] == "FAIL":
        print("INSPECTION FAILED:")
        for err in report["errors"]:
            print(f"  [!] {err}")
        print("=" * 80)
        return

    print("APPLICATION TABLES AUDIT:")
    for t_name in EXPECTED_APPLICATION_TABLES:
        stats = report["application_table_stats"].get(t_name, {})
        if stats.get("exists"):
            count = stats.get("row_count", 0)
            status_text = "EXISTS (EMPTY)" if count == 0 else f"EXISTS ({count} rows)"
            print(f"  • {t_name:<25} : [FOUND]  {status_text}")
        else:
            print(f"  • {t_name:<25} : [ABSENT] Not yet created")

    print("-" * 80)
    print("SCHEMA INVENTORY SUMMARY:")
    print(f"  • Total Public Tables Discovered : {len(report['all_public_tables'])}")
    print(f"  • Application Tables Present     : {len(report['expected_tables_found'])} / {len(EXPECTED_APPLICATION_TABLES)}")
    print(f"  • Unexpected / Other Tables      : {len(report['unexpected_tables'])}")
    if report["unexpected_tables"]:
        for u in report["unexpected_tables"]:
            print(f"      - {u}")

    if report["schema_details"]:
        print("-" * 80)
        print("TABLE DETAILS (CONSTRAINTS & KEYS):")
        for t_name, details in report["schema_details"].items():
            if t_name in EXPECTED_APPLICATION_TABLES:
                col_cnt = len(details.get("columns", []))
                pks = details.get("primary_key", [])
                fks = details.get("foreign_keys", [])
                idxs = details.get("indexes", [])
                pk_str = f"PK={pks}" if pks else "NO PK"
                fk_str = f"{len(fks)} FK(s)" if fks else "0 FKs"
                idx_str = f"{len(idxs)} index(es)"
                print(f"  • {t_name:<25} : {col_cnt} columns | {pk_str} | {fk_str} | {idx_str}")

    print("-" * 80)
    if report["warnings"]:
        print("NOTICES & WARNINGS:")
        for w in report["warnings"]:
            print(f"  [*] {w}")
        print("-" * 80)

    print(f"TARGET SUITABILITY: {'SUITABLE' if report['is_suitable_for_migration'] else 'NOT SUITABLE'}")
    print(f"ASSESSMENT        : {report['suitability_assessment']}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Inspect Supabase PostgreSQL Target Database Schema and Tables")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Path to .env configuration file")
    parser.add_argument("--target-db", type=str, default=None, help="Explicit target database URL override")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    args = parser.parse_args()

    target_url, source_info = load_target_url(args.env_file, args.target_db)

    if not target_url:
        print("=" * 80)
        print("  KPRIET SMART HOSTEL - SUPABASE TARGET DATABASE INSPECTION (READ-ONLY)")
        print("=" * 80)
        print(f"[FAIL] Target configuration error: {source_info}")
        print("To configure:")
        print("  1. Copy backend/.env.example to backend/.env")
        print("  2. Fill in DATABASE_URL with your Supabase PostgreSQL connection string.")
        print("=" * 80)
        sys.exit(1)

    report = inspect_target_database(target_url)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_inspection_report(report)

    sys.exit(0 if report["status"] == "PASS" else 1)

if __name__ == "__main__":
    main()
