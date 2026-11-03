#!/usr/bin/env python3
"""
test_render_readiness.py - Comprehensive Render Production Readiness Test Suite
KPRIET Smart Hostel Attendance Management System

Validates:
1. Production database guard:
   - Rejection of missing DATABASE_URL in production.
   - Rejection of SQLite URLs in production.
   - Acceptance and normalization of PostgreSQL production URLs.
   - Development SQLite default and support.
2. Supabase Cloud Storage service:
   - Successful photo upload via REST API mock.
   - Safe failure handling on cloud upload failure.
   - Handling of missing cloud credentials.
3. Persistent student photo registration:
   - Stable object path / reference format in PostgreSQL (/uploads/profiles/{filename}).
   - Never storing temporary signed URLs.
   - Zero broken photo references when upload fails in production.
   - Safe unique filenames containing register number and hex UUID.
   - Development fallback to local storage.
4. Authenticated photo retrieval proxy:
   - 401 Unauthorized for unauthenticated requests.
   - 400 Bad Request on path traversal attempts.
   - 200 OK for authorized staff.
   - 200 OK for student accessing their own photo.
   - 403 Forbidden for student accessing another student's photo.
   - Private caching header verification.
"""

import os
import sys
import uuid
import base64
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure local test runner uses local SQLite database for test execution
LOCAL_DB_PATH = BACKEND_DIR / "smart_hostel.db"
os.environ["DATABASE_URL"] = f"sqlite:///{LOCAL_DB_PATH.as_posix()}"
os.environ["ENVIRONMENT"] = "development"

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.database import validate_database_url, SessionLocal
from app.models import Student, Staff
from app.security import create_access_token
from app.services.storage_service import (
    generate_unique_photo_filename,
    upload_photo_to_supabase,
    save_profile_photo,
    delete_profile_photo,
    UPLOAD_DIR
)
from app.main import get_profile_photo

# Sample valid 1x1 JPEG in base64
SAMPLE_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////"
    "////////////////////////////////////////////////////wgALCAABAAEBAREA"
    "/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)

class TestRenderDatabaseGuard(unittest.TestCase):
    """FIX 2: Production Database Guard Tests"""

    def test_production_missing_database_url(self):
        """Production must raise RuntimeError if DATABASE_URL is missing or None."""
        with self.assertRaises(RuntimeError) as ctx:
            validate_database_url(None, environment="production")
        self.assertIn("DATABASE_URL environment variable is missing", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx:
            validate_database_url("   ", environment="production")
        self.assertIn("DATABASE_URL environment variable is missing", str(ctx.exception))

    def test_production_sqlite_rejection(self):
        """Production must strictly reject SQLite URLs."""
        test_cases = [
            "sqlite:///./smart_hostel.db",
            "sqlite:///:memory:",
            "sqlite:///d:/hostel.db",
            "SQLITE:///./test.db",
        ]
        for url in test_cases:
            with self.subTest(url=url):
                with self.assertRaises(RuntimeError) as ctx:
                    validate_database_url(url, environment="production")
                self.assertIn("configured for SQLite", str(ctx.exception))

    def test_production_valid_postgres_url(self):
        """Production must accept and normalize PostgreSQL URLs."""
        # 1. postgres:// -> postgresql+psycopg2://
        u1 = validate_database_url(
            "postgres://postgres:secret@db.xyz.supabase.co:5432/postgres",
            environment="production"
        )
        self.assertTrue(u1.startswith("postgresql+psycopg2://"))
        self.assertIn("db.xyz.supabase.co", u1)

        # 2. postgresql:// -> postgresql+psycopg2://
        u2 = validate_database_url(
            "postgresql://postgres:secret@db.xyz.supabase.co:5432/postgres",
            environment="production"
        )
        self.assertTrue(u2.startswith("postgresql+psycopg2://"))

        # 3. Already normalized
        u3 = validate_database_url(
            "postgresql+psycopg2://postgres:secret@db.xyz.supabase.co:5432/postgres",
            environment="production"
        )
        self.assertTrue(u3.startswith("postgresql+psycopg2://"))

    def test_development_sqlite_support(self):
        """Development must safely fall back to SQLite when DATABASE_URL is not set."""
        u_default = validate_database_url(None, environment="development")
        self.assertEqual(u_default, "sqlite:///./smart_hostel.db")

        u_custom = validate_database_url("sqlite:///./custom.db", environment="development")
        self.assertEqual(u_custom, "sqlite:///./custom.db")


class TestSupabaseStorageService(unittest.TestCase):
    """FIX 3: Cloud Storage & Persistent Uploads Tests"""

    def test_unique_filename_generation(self):
        """Filenames must be safe, unique, and deterministically prefixed with register number."""
        fn1 = generate_unique_photo_filename("711321104001")
        fn2 = generate_unique_photo_filename("711321104001")

        self.assertTrue(fn1.startswith("711321104001_"))
        self.assertTrue(fn1.endswith(".jpg"))
        self.assertNotEqual(fn1, fn2, "Subsequent calls for the same register number must be distinct.")
        self.assertTrue(len(fn1.split("_")[1]) >= 8)

    @patch("httpx.Client")
    def test_supabase_upload_success(self, mock_client_cls):
        """Verifies upload_photo_to_supabase succeeds with HTTP 200/201 response."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-key-12345",
            "SUPABASE_BUCKET": "student-profiles",
        }):
            ok, msg = upload_photo_to_supabase("test_photo.jpg", b"fake_bytes")
            self.assertTrue(ok)
            self.assertEqual(msg, "UPLOAD_SUCCESS")
            # Verify x-upsert: false was passed
            mock_client.post.assert_called_once()
            args, kwargs = mock_client.post.call_args
            self.assertEqual(kwargs["headers"]["x-upsert"], "false")

    @patch("httpx.Client")
    def test_supabase_upload_failure(self, mock_client_cls):
        """Verifies upload_photo_to_supabase handles network or HTTP errors safely."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-key-12345",
            "SUPABASE_BUCKET": "student-profiles",
        }):
            ok, msg = upload_photo_to_supabase("test_photo.jpg", b"fake_bytes")
            self.assertFalse(ok)
            self.assertIn("HTTP 403", msg)

    @patch("app.services.storage_service.upload_photo_to_supabase")
    def test_save_profile_photo_production_success(self, mock_upload):
        """In production, successful cloud upload returns stable canonical path."""
        mock_upload.return_value = (True, "UPLOAD_SUCCESS")

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            url = save_profile_photo("711321104001", SAMPLE_JPEG_B64)
            self.assertIsNotNone(url)
            self.assertTrue(url.startswith("/uploads/profiles/711321104001_"))
            self.assertTrue(url.endswith(".jpg"))

    @patch("app.services.storage_service.upload_photo_to_supabase")
    def test_save_profile_photo_production_failure_no_broken_reference(self, mock_upload):
        """In production, failed cloud upload returns None (prevents broken references in DB)."""
        mock_upload.return_value = (False, "Network timeout")

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            url = save_profile_photo("711321104001", SAMPLE_JPEG_B64)
            self.assertIsNone(url, "Must return None on cloud upload failure in production.")

    def test_save_profile_photo_development_fallback(self):
        """In development, local disk storage is used when no cloud keys are configured."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            # Unset supabase keys to test offline mode
            os.environ.pop("SUPABASE_URL", None)
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)

            url = save_profile_photo("TESTDEV001", SAMPLE_JPEG_B64)
            self.assertIsNotNone(url)
            self.assertTrue(url.startswith("/uploads/profiles/TESTDEV001_"))

            # Verify local file was created
            filename = Path(url).name
            local_file = UPLOAD_DIR / filename
            self.assertTrue(local_file.exists(), f"Local file {local_file} must exist.")

            # Cleanup
            delete_profile_photo(filename)
            self.assertFalse(local_file.exists(), "delete_profile_photo must clean up local file.")


class TestAuthenticatedPhotoRetrievalProxy(unittest.TestCase):
    """FIX 3 / FIX 4: Authenticated Photo Retrieval Endpoint Security Tests"""

    def setUp(self):
        self.db = SessionLocal()
        # Find students with photos
        self.students = self.db.query(Student).filter(
            Student.profile_photo_url.isnot(None),
            Student.profile_photo_url != ""
        ).all()
        self.staff = self.db.query(Staff).first()

    def tearDown(self):
        self.db.close()

    def test_unauthenticated_request_rejected(self):
        """Unauthenticated requests must be blocked with HTTP 401."""
        if not self.students:
            self.skipTest("No students found in DB.")
        photo_filename = Path(self.students[0].profile_photo_url).name

        with self.assertRaises(HTTPException) as ctx:
            get_profile_photo(filename=photo_filename, token=None, credentials=None, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_path_traversal_rejected(self):
        """Path traversal attempts (../, /, \\) must be rejected with HTTP 400."""
        malicious_filenames = [
            "../../etc/passwd",
            "..\\..\\windows\\system32\\cmd.exe",
            "profiles/sub/photo.jpg",
            "photo.jpg.exe",
        ]
        for fn in malicious_filenames:
            with self.subTest(filename=fn):
                with self.assertRaises(HTTPException) as ctx:
                    get_profile_photo(filename=fn, token="fake_token", credentials=None, db=self.db)
                self.assertEqual(ctx.exception.status_code, 400)

    def test_authorized_staff_can_access_any_photo(self):
        """Staff members are authorized to retrieve any student photo."""
        if not self.students or not self.staff:
            self.skipTest("Need staff and students in DB.")

        photo_filename = Path(self.students[0].profile_photo_url).name
        token = create_access_token({
            "sub": str(self.staff.id),
            "role": self.staff.role,
            "identifier": self.staff.staff_id
        })
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        resp = get_profile_photo(filename=photo_filename, token=None, credentials=cred, db=self.db)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Cache-Control", resp.headers)
        self.assertIn("private", resp.headers["Cache-Control"])
        self.assertIn("no-store", resp.headers["Cache-Control"])

    def test_student_can_access_own_photo(self):
        """A student is authorized to retrieve their own photo."""
        if not self.students:
            self.skipTest("Need students in DB.")

        student = self.students[0]
        photo_filename = Path(student.profile_photo_url).name
        token = create_access_token({
            "sub": str(student.id),
            "role": "student",
            "identifier": student.register_number
        })
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        resp = get_profile_photo(filename=photo_filename, token=None, credentials=cred, db=self.db)
        self.assertEqual(resp.status_code, 200)

    def test_student_cannot_access_other_student_photo(self):
        """A student must be rejected with HTTP 403 when requesting another student's photo."""
        if len(self.students) < 2:
            self.skipTest("Need at least 2 students in DB.")

        student_a = self.students[0]
        student_b = self.students[1]
        photo_b_filename = Path(student_b.profile_photo_url).name

        # Token for Student A requesting Student B's photo
        token_a = create_access_token({
            "sub": str(student_a.id),
            "role": "student",
            "identifier": student_a.register_number
        })
        cred_a = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_a)

        with self.assertRaises(HTTPException) as ctx:
            get_profile_photo(filename=photo_b_filename, token=None, credentials=cred_a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)


def main():
    print("=" * 80)
    print("  KPRIET SMART HOSTEL - RENDER PRODUCTION READINESS TEST SUITE")
    print("=" * 80)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("=" * 80)
    print("  ALL RENDER PRODUCTION READINESS TESTS PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    main()
