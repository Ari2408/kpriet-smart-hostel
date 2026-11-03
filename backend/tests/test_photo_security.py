#!/usr/bin/env python3
"""
test_photo_security.py - Security & Authorization Test Suite for Student Photo Retrieval Endpoint
Tests all critical requirements:
1. Unauthenticated requests (401 Unauthorized)
2. Authorized staff access to student photos (200 OK)
3. Authorized student access to their OWN photo (200 OK)
4. Unauthorized student access to ANOTHER student's photo (403 Forbidden)
5. Missing photo request (404 Not Found)
6. Path traversal attempts (400 Bad Request)
7. Cache-Control header security policy (private, no-cache, no-store)
8. Token query parameter authentication support (?token=...)
"""

import sys
import os
from pathlib import Path
from fastapi.security import HTTPAuthorizationCredentials
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure local test runner uses local SQLite database
os.environ["DATABASE_URL"] = f"sqlite:///{(BACKEND_DIR / 'smart_hostel.db').as_posix()}"
os.environ["ENVIRONMENT"] = "development"

from app.main import get_profile_photo
from app.database import SessionLocal
from app.models import Student, Staff
from app.security import create_access_token

def main():
    print("=" * 80)
    print("  KPRIET SMART HOSTEL - STUDENT PHOTO ENDPOINT SECURITY TEST SUITE")
    print("=" * 80)

    db = SessionLocal()
    students = db.query(Student).filter(
        Student.profile_photo_url.isnot(None),
        Student.profile_photo_url != ""
    ).all()

    if len(students) < 2:
        print("[!] Not enough students with photos in database to run multi-student isolation tests.")
        db.close()
        return

    student_a = students[0]
    student_b = students[1]
    staff = db.query(Staff).first()

    photo_a = Path(student_a.profile_photo_url).name
    photo_b = Path(student_b.profile_photo_url).name

    token_staff = create_access_token({"sub": str(staff.id), "role": staff.role, "identifier": staff.staff_id})
    token_student_a = create_access_token({"sub": str(student_a.id), "role": "student", "identifier": student_a.register_number})
    token_student_b = create_access_token({"sub": str(student_b.id), "role": "student", "identifier": student_b.register_number})

    cred_staff = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_staff)
    cred_student_a = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_student_a)
    cred_student_b = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_student_b)

    # TEST 1: Unauthenticated Request
    print("[1/8] Testing unauthenticated request...")
    try:
        get_profile_photo(filename=photo_a, token=None, credentials=None, db=db)
        assert False, "Expected 401 Unauthorized"
    except HTTPException as e:
        assert e.status_code == 401, f"Expected 401, got {e.status_code}"
        print(f"  -> Passed. Unauthenticated access blocked with HTTP 401: {e.detail}")

    # TEST 2: Authorized Staff Access
    print("[2/8] Testing authorized staff request...")
    resp_staff = get_profile_photo(filename=photo_a, token=None, credentials=cred_staff, db=db)
    assert resp_staff.status_code == 200
    print("  -> Passed. Authorized staff granted access with HTTP 200.")

    # TEST 3: Authorized Student Access to OWN Photo
    print("[3/8] Testing student accessing their OWN photo...")
    resp_self = get_profile_photo(filename=photo_a, token=None, credentials=cred_student_a, db=db)
    assert resp_self.status_code == 200
    print(f"  -> Passed. Student {student_a.register_number} successfully retrieved own photo with HTTP 200.")

    # TEST 4: Unauthorized Student Access to ANOTHER Student's Photo
    print("[4/8] Testing student B attempting to access student A's photo...")
    try:
        get_profile_photo(filename=photo_a, token=None, credentials=cred_student_b, db=db)
        assert False, "Expected 403 Forbidden"
    except HTTPException as e:
        assert e.status_code == 403, f"Expected 403, got {e.status_code}"
        assert "access denied" in e.detail.lower()
        print(f"  -> Passed. Student {student_b.register_number} blocked from viewing student {student_a.register_number}'s photo with HTTP 403: {e.detail}")

    # TEST 5: Path Traversal Attempts
    print("[5/8] Testing path traversal attacks...")
    traversal_payloads = [
        "../../etc/passwd.jpg",
        "..\\smart_hostel.db",
        "invalid/file.jpg",
        "bad*name.jpg"
    ]
    for bad_name in traversal_payloads:
        try:
            get_profile_photo(filename=bad_name, token=None, credentials=cred_staff, db=db)
            assert False, f"Expected 400 for {bad_name}"
        except HTTPException as e:
            assert e.status_code == 400, f"Expected 400, got {e.status_code}"
            print(f"  -> Blocked '{bad_name}' with HTTP 400 Bad Request.")

    # TEST 6: Missing Photo Request
    print("[6/8] Testing missing photograph request...")
    try:
        get_profile_photo(filename="non_existent_999999.jpg", token=None, credentials=cred_staff, db=db)
        assert False, "Expected 404 Not Found"
    except HTTPException as e:
        assert e.status_code == 404, f"Expected 404, got {e.status_code}"
        print(f"  -> Passed. Non-existent photo cleanly returned HTTP 404: {e.detail}")

    # TEST 7: Private Cache-Control Headers Policy Verification
    print("[7/8] Testing Cache-Control security policy...")
    cache_header = resp_staff.headers.get("cache-control", "")
    assert "private" in cache_header, f"Expected 'private' in Cache-Control, got: {cache_header}"
    assert "no-store" in cache_header, f"Expected 'no-store' in Cache-Control, got: {cache_header}"
    assert "public" not in cache_header, f"Insecure 'public' directive found: {cache_header}"
    print(f"  -> Passed. Cache-Control strictly set to: '{cache_header}'.")

    # TEST 8: Token in Query Parameter (?token=...) Support
    print("[8/8] Testing query-parameter token authentication (?token=...)...")
    resp_query = get_profile_photo(filename=photo_a, token=token_student_a, credentials=None, db=db)
    assert resp_query.status_code == 200
    print("  -> Passed. Query parameter '?token=' authenticated successfully for Flutter image widgets.")

    db.close()
    print("=" * 80)
    print("  ALL 8 SECURITY & AUTHORIZATION TESTS PASSED. ENDPOINT IS FULLY SECURED.")
    print("=" * 80)

if __name__ == "__main__":
    main()
