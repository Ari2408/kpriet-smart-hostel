import sys
import os
import pytest
import datetime
import json
import base64
import numpy as np
import cv2
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import SystemConfig, Staff, Student, Attendance
from app.security import create_access_token, hash_password
from app.services.face_service import extract_face_embedding
from app.seed import create_synthetic_portrait

client = TestClient(app)

def create_face_b64(seed_offset: int = 0) -> str:
    img = np.full((240, 240, 3), 240, dtype=np.uint8)
    cv2.circle(img, (120, 120), 80, (20 + seed_offset, 20, 40), -1)
    cv2.circle(img, (120, 125), 65, (160, 190, 225), -1)
    cv2.circle(img, (95, 110), 8, (30, 30, 30), -1)
    cv2.circle(img, (145, 110), 8, (30, 30, 30), -1)
    cv2.line(img, (120, 118), (120, 142), (110, 140, 180), 3)
    cv2.ellipse(img, (120, 156), (24, 10), 0, 0, 180, (50, 60, 160), 3)
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

def create_different_face_b64() -> str:
    img = np.full((240, 240, 3), 100, dtype=np.uint8)
    # Completely different geometric shape (square blocks and distinct layout)
    cv2.rectangle(img, (70, 70), (170, 180), (130, 150, 190), -1)
    cv2.circle(img, (85, 90), 12, (200, 20, 20), -1)
    cv2.circle(img, (155, 90), 12, (200, 20, 20), -1)
    cv2.line(img, (120, 110), (120, 145), (10, 10, 10), 5)
    cv2.rectangle(img, (90, 160), (150, 175), (20, 20, 180), -1)
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

@pytest.fixture(scope="module")
def setup_test_data():
    db = SessionLocal()
    # Ensure config
    config = db.query(SystemConfig).first()
    if not config:
        config = SystemConfig(
            campus_name="KPR Institute of Engineering and Technology",
            campus_latitude=11.05445,
            campus_longitude=77.08641,
            geofence_radius_meters=600.0,
            attendance_start_time="19:00",
            attendance_end_time="20:00"
        )
        db.add(config)
        db.commit()

    # Get student
    student = db.query(Student).filter(Student.register_number == "711321104001").first()
    if not student:
        student = db.query(Student).first()
    staff = db.query(Staff).filter(Staff.email == "staff@kpriet.ac.in").first()
    if not staff:
        staff = db.query(Staff).first()

    student_token = create_access_token({
        "sub": str(student.id),
        "role": "student",
        "name": student.name,
        "email": student.email,
        "identifier": student.register_number
    })

    staff_token = create_access_token({
        "sub": str(staff.id),
        "role": "staff",
        "name": staff.name,
        "email": staff.email,
        "identifier": staff.staff_id
    })

    # Clear today's attendance for student 1 if any exists
    today = datetime.date.today()
    db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.attendance_date == today
    ).delete()
    db.commit()

    student_id = student.id
    student_name = student.name
    staff_id = staff.id
    c_lat = config.campus_latitude
    c_lon = config.campus_longitude

    db.close()
    return {
        "student_id": student_id,
        "student_name": student_name,
        "staff_id": staff_id,
        "student_token": student_token,
        "staff_token": staff_token,
        "campus_lat": c_lat,
        "campus_lon": c_lon
    }

# 1. Test Geofence validation - Inside Campus
def test_location_inside_campus(setup_test_data):
    lat = setup_test_data["campus_lat"] + 0.0001
    lon = setup_test_data["campus_lon"] + 0.0001
    response = client.post("/api/attendance/verify-location", json={
        "latitude": lat,
        "longitude": lon,
        "is_mock": False
    })
    assert response.status_code == 200
    data = response.json()
    assert data["inside_geofence"] is True
    assert data["distance_meters"] < 600.0

# 2. Test Geofence validation - Outside Campus
def test_location_outside_campus(setup_test_data):
    # Location 20 km away
    lat = setup_test_data["campus_lat"] + 0.2
    lon = setup_test_data["campus_lon"] + 0.2
    response = client.post("/api/attendance/verify-location", json={
        "latitude": lat,
        "longitude": lon,
        "is_mock": False
    })
    assert response.status_code == 200
    data = response.json()
    assert data["inside_geofence"] is False
    assert "outside the college campus" in data["message"].lower()

# 3. Test Mock Location Rejection
def test_mock_location_rejected(setup_test_data):
    lat = setup_test_data["campus_lat"]
    lon = setup_test_data["campus_lon"]
    response = client.post("/api/attendance/verify-location", json={
        "latitude": lat,
        "longitude": lon,
        "is_mock": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["inside_geofence"] is False
    assert "mock" in data["message"].lower()

# 4. Test Attendance Submission: Outside Campus (rejected)
def test_attendance_outside_campus_rejected(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    face_b64 = create_face_b64()
    response = client.post("/api/attendance/submit", headers=headers, json={
        "latitude": setup_test_data["campus_lat"] + 0.15,
        "longitude": setup_test_data["campus_lon"] + 0.15,
        "face_image_base64": face_b64,
        "test_time_override": "19:30"
    })
    assert response.status_code == 400
    assert "outside the college campus" in response.json()["detail"].lower()

# 5. Test Attendance Submission: Before 7 PM (rejected)
def test_attendance_before_7pm_rejected(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    face_b64 = create_face_b64()
    response = client.post("/api/attendance/submit", headers=headers, json={
        "latitude": setup_test_data["campus_lat"],
        "longitude": setup_test_data["campus_lon"],
        "face_image_base64": face_b64,
        "test_time_override": "18:45"
    })
    assert response.status_code == 400
    assert "not opened yet" in response.json()["detail"].lower()

# 6. Test Attendance Submission: After 8 PM (rejected)
def test_attendance_after_8pm_rejected(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    face_b64 = create_face_b64()
    response = client.post("/api/attendance/submit", headers=headers, json={
        "latitude": setup_test_data["campus_lat"],
        "longitude": setup_test_data["campus_lon"],
        "face_image_base64": face_b64,
        "test_time_override": "20:15"
    })
    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()

# 7. Test Attendance Submission: Non-matching Face (rejected)
def test_attendance_non_matching_face_rejected(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    diff_face = create_different_face_b64()
    response = client.post("/api/attendance/submit", headers=headers, json={
        "latitude": setup_test_data["campus_lat"],
        "longitude": setup_test_data["campus_lon"],
        "face_image_base64": diff_face,
        "test_time_override": "19:30"
    })
    assert response.status_code == 400
    assert "face verification failed" in response.json()["detail"].lower()

# 8. Test Attendance Submission: Valid (Inside campus, correct window, matching face)
def test_attendance_valid_submission(setup_test_data):
    db = SessionLocal()
    db.query(Attendance).filter(
        Attendance.student_id == setup_test_data["student_id"],
        Attendance.attendance_date == datetime.date.today()
    ).delete()
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    face_b64 = create_face_b64()
    response = client.post("/api/attendance/submit", headers=headers, json={
        "latitude": setup_test_data["campus_lat"] + 0.0001,
        "longitude": setup_test_data["campus_lon"] + 0.0001,
        "face_image_base64": face_b64,
        "test_time_override": "19:30"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PRESENT"
    assert "successfully registered" in data["message"].lower()

# 9. Test Duplicate Attendance Prevention
def test_attendance_duplicate_rejected(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    face_b64 = create_face_b64()
    response = client.post("/api/attendance/submit", headers=headers, json={
        "latitude": setup_test_data["campus_lat"] + 0.0001,
        "longitude": setup_test_data["campus_lon"] + 0.0001,
        "face_image_base64": face_b64,
        "test_time_override": "19:35"
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()

# 10. Test Student Dashboard & Attendance Percentage Formula
def test_student_dashboard(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    response = client.get("/api/attendance/dashboard/student", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["register_number"] == "711321104001"
    assert data["today_status"] == "PRESENT"
    assert "attendance_percentage" in data
    assert 0.0 <= data["attendance_percentage"] <= 100.0
    assert data["total_present_days"] > 0

# 11. Test Staff Adding Student with Photo & Face Profile
def test_staff_add_student(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['staff_token']}"}
    import uuid
    uid = uuid.uuid4().hex[:6]
    reg_no = f"71132{uid}"
    face_b64 = create_face_b64()
    payload = {
        "student_id": f"KPR22CS{uid}",
        "register_number": reg_no,
        "name": "Muthu Kumar P",
        "email": f"muthu_{uid}@kpriet.ac.in",
        "password": "Password@123",
        "department": "Computer Science & Engineering",
        "academic_year": 3,
        "hostel_block": "Emerald Block",
        "room_number": "B-305",
        "phone_number": "+91 99887 76655",
        "profile_image_base64": face_b64
    }
    response = client.post("/api/students", headers=headers, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["register_number"] == reg_no
    assert data["name"] == "Muthu Kumar P"

# 12. Test Staff Dashboard & Absentee Identification
def test_staff_dashboard_and_absentees(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['staff_token']}"}
    response = client.get("/api/attendance/dashboard/staff", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] >= 6
    assert data["present_today"] >= 1

    # Absentee endpoint
    abs_resp = client.get("/api/attendance/absentees", headers=headers)
    assert abs_resp.status_code == 200
    abs_data = abs_resp.json()
    assert isinstance(abs_data, list)
    # The unregistered students should appear in absentees list
    assert any(s["register_number"] == "711321104002" for s in abs_data)

# 13. Test CSV and PDF Report Generation
def test_report_generation(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['staff_token']}"}
    csv_resp = client.get("/api/reports/export/csv", headers=headers)
    assert csv_resp.status_code == 200
    assert "Record ID,Student Name" in csv_resp.text

    pdf_resp = client.get("/api/reports/export/pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")

# 14. Test Live Verification Session & Randomized Liveness Challenge Success
def test_liveness_challenge_success(setup_test_data):
    # Clear today's attendance so mark can succeed
    db = SessionLocal()
    db.query(Attendance).filter(
        Attendance.student_id == setup_test_data["student_id"],
        Attendance.attendance_date == datetime.date.today()
    ).delete()
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    res_start = client.post("/api/attendance/start-verification", headers=headers)
    assert res_start.status_code == 200
    sess_data = res_start.json()
    assert "session_token" in sess_data
    assert "challenge_type" in sess_data
    token = sess_data["session_token"]
    challenge = sess_data["challenge_type"]

    # Verify with matching challenge
    face_b64 = create_face_b64()
    res_verify = client.post("/api/attendance/verify-face", headers=headers, json={
        "session_token": token,
        "face_image_base64": face_b64,
        "challenge_action_detected": challenge
    })
    assert res_verify.status_code == 200
    assert res_verify.json()["verified"] is True
    assert res_verify.json()["liveness_passed"] is True

    # Mark attendance with valid session
    res_mark = client.post("/api/attendance/mark", headers=headers, json={
        "session_token": token,
        "latitude": setup_test_data["campus_lat"] + 0.0001,
        "longitude": setup_test_data["campus_lon"] + 0.0001,
        "test_time_override": "19:40"
    })
    assert res_mark.status_code == 200
    assert res_mark.json()["status"] == "PRESENT"

# 15. Test Failed Liveness Challenge (Action Mismatch)
def test_liveness_challenge_mismatch_rejected(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    res_start = client.post("/api/attendance/start-verification", headers=headers)
    assert res_start.status_code == 200
    sess_data = res_start.json()
    token = sess_data["session_token"]
    expected_challenge = sess_data["challenge_type"]
    wrong_challenge = "TURN_HEAD_RIGHT" if expected_challenge != "TURN_HEAD_RIGHT" else "BLINK_TWICE"

    face_b64 = create_face_b64()
    res_verify = client.post("/api/attendance/verify-face", headers=headers, json={
        "session_token": token,
        "face_image_base64": face_b64,
        "challenge_action_detected": wrong_challenge
    })
    assert res_verify.status_code == 200
    assert res_verify.json()["verified"] is False
    assert "challenge failed" in res_verify.json()["message"].lower()

# 16. Test Replay Attack with Reused Session Token
def test_replay_used_verification_session_rejected(setup_test_data):
    # Clear today's attendance so first submission succeeds and burns the token
    db = SessionLocal()
    db.query(Attendance).filter(
        Attendance.student_id == setup_test_data["student_id"],
        Attendance.attendance_date == datetime.date.today()
    ).delete()
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {setup_test_data['student_token']}"}
    res_start = client.post("/api/attendance/start-verification", headers=headers)
    token = res_start.json()["session_token"]
    challenge = res_start.json()["challenge_type"]

    face_b64 = create_face_b64()
    client.post("/api/attendance/verify-face", headers=headers, json={
        "session_token": token,
        "face_image_base64": face_b64,
        "challenge_action_detected": challenge
    })
    # First submit burns the token
    client.post("/api/attendance/mark", headers=headers, json={
        "session_token": token,
        "latitude": setup_test_data["campus_lat"] + 0.0001,
        "longitude": setup_test_data["campus_lon"] + 0.0001,
        "test_time_override": "19:42"
    })
    # Second attempt must be rejected as replay
    replay_resp = client.post("/api/attendance/mark", headers=headers, json={
        "session_token": token,
        "latitude": setup_test_data["campus_lat"] + 0.0001,
        "longitude": setup_test_data["campus_lon"] + 0.0001,
        "test_time_override": "19:43"
    })
    assert replay_resp.status_code == 400
    assert "already been submitted" in replay_resp.json()["detail"].lower() or "replay" in replay_resp.json()["detail"].lower()

# 17. Test Warden-Created Password & Student Login
def test_warden_creates_student_and_student_logins(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['staff_token']}"}
    import uuid
    uid = uuid.uuid4().hex[:6]
    reg_no = f"71139{uid}"
    initial_pwd = "WardenCreatedPass@123"

    payload = {
        "register_number": reg_no,
        "name": "Kavitha S",
        "email": f"kavitha_{uid}@kpriet.ac.in",
        "password": initial_pwd,
        "confirm_password": initial_pwd,
        "department": "Information Technology",
        "academic_year": 2,
        "hostel_block": "Coral Block",
        "room_number": "C-102",
        "phone_number": "+91 91234 56789",
        "profile_image_base64": create_face_b64(seed_offset=5)
    }
    create_resp = client.post("/api/students", headers=headers, json=payload)
    assert create_resp.status_code == 201

    # Student logs in with warden-created password
    login_resp = client.post("/api/auth/login", json={
        "username": reg_no,
        "password": initial_pwd,
        "role_hint": "student"
    })
    assert login_resp.status_code == 200
    assert login_resp.json()["name"] == "Kavitha S"

# 18. Test Student Self-Service Password Change
def test_student_changes_password(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['staff_token']}"}
    import uuid
    uid = uuid.uuid4().hex[:6]
    reg_no = f"71138{uid}"

    client.post("/api/students", headers=headers, json={
        "register_number": reg_no,
        "name": "Arun Kumar",
        "password": "InitialPassword@123",
        "department": "CSE",
        "academic_year": 1,
        "hostel_block": "Emerald Block",
        "room_number": "E-101",
        "profile_image_base64": create_face_b64()
    })

    # Student logs in
    login_resp = client.post("/api/auth/login", json={
        "username": reg_no,
        "password": "InitialPassword@123"
    })
    st_token = login_resp.json()["access_token"]
    st_headers = {"Authorization": f"Bearer {st_token}"}

    # Change password
    change_resp = client.post("/api/auth/change-password", headers=st_headers, json={
        "current_password": "InitialPassword@123",
        "new_password": "NewStudentPassword@456"
    })
    assert change_resp.status_code == 200
    assert change_resp.json()["success"] is True

    # Old password rejected
    old_login = client.post("/api/auth/login", json={
        "username": reg_no,
        "password": "InitialPassword@123"
    })
    assert old_login.status_code == 401

    # New password works
    new_login = client.post("/api/auth/login", json={
        "username": reg_no,
        "password": "NewStudentPassword@456"
    })
    assert new_login.status_code == 200

# 19. Test Permanent Deletion, Biometric Purge, and Anonymized Historical Reporting
def test_permanent_delete_purges_biometrics_and_anonymizes_reports(setup_test_data):
    headers = {"Authorization": f"Bearer {setup_test_data['staff_token']}"}
    import uuid
    uid = uuid.uuid4().hex[:6]
    reg_no = f"71137{uid}"
    pwd = "DeleteTest@123"

    # 1. Create student
    create_res = client.post("/api/students", headers=headers, json={
        "register_number": reg_no,
        "name": "Temporary Student",
        "password": pwd,
        "department": "Mechanical Engineering",
        "academic_year": 4,
        "hostel_block": "Ruby Block",
        "room_number": "R-101",
        "profile_image_base64": create_face_b64()
    })
    assert create_res.status_code == 201
    st_id = create_res.json()["id"]

    # 2. Add attendance record for this student
    db = SessionLocal()
    att = Attendance(
        student_id=st_id,
        attendance_date=datetime.date(2026, 10, 15),
        attendance_time=datetime.time(19, 30),
        latitude=11.05445,
        longitude=77.08641,
        distance_from_campus=50.0,
        face_confidence=0.92,
        status="PRESENT",
        remarks="Test historical record"
    )
    db.add(att)
    db.commit()
    att_id = att.id
    db.close()

    # 3. Confirmation register number mismatch rejected
    bad_del = client.delete(f"/api/students/{st_id}?confirm_register_number=WRONG_NUMBER", headers=headers)
    assert bad_del.status_code == 400

    # 4. Successful permanent deletion
    del_res = client.delete(f"/api/students/{st_id}?confirm_register_number={reg_no}", headers=headers)
    assert del_res.status_code == 200
    assert "permanently deleted" in del_res.json()["message"].lower()

    # 5. Deleted student cannot log in
    del_login = client.post("/api/auth/login", json={
        "username": reg_no,
        "password": pwd
    })
    assert del_login.status_code == 401

    # 6. Biometric profile and PII removed
    db = SessionLocal()
    st_check = db.query(Student).filter(Student.id == st_id).first()
    assert st_check is None

    # 7. Attendance record anonymized without PII
    att_check = db.query(Attendance).filter(Attendance.id == att_id).first()
    assert att_check is not None
    assert att_check.student_id is None
    assert att_check.is_anonymized is True
    assert att_check.anonymized_department == "Mechanical Engineering"
    db.close()

    # 8. Historical reports still work with anonymized data
    rep_res = client.get("/api/reports/summary", headers=headers)
    assert rep_res.status_code == 200
    assert rep_res.json()["total_records"] > 0

