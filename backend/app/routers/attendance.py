import datetime
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from ..database import get_db
from ..models import Attendance, Student, SystemConfig, VerificationSession
from ..schemas import (
    LocationVerifyRequest, LocationVerifyResponse,
    AttendanceSubmission, AttendanceResponse,
    AttendanceRecordItem, StudentDashboardResponse,
    StaffDashboardResponse, AbsentStudentItem,
    StartVerificationResponse, VerifyFaceRequest,
    VerifyFaceResponse, MarkAttendanceRequest
)
from ..security import get_current_user, require_staff, require_student
from ..services.geofence_service import validate_geofence, haversine_distance
from ..services.face_service import (
    verify_live_face, get_random_challenge,
    verify_live_face_with_challenge
)
from ..services.attendance_service import (
    get_current_system_config, is_within_attendance_window,
    calculate_student_stats, get_today_student_status,
    get_staff_today_summary, parse_time_str,
    get_ist_now, get_ist_today, get_ist_time
)

router = APIRouter(prefix="/api/attendance", tags=["Attendance Management"])

@router.post("/verify-location", response_model=LocationVerifyResponse)
def verify_location(
    payload: LocationVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Step 1 of Attendance Check: Verifies whether student is physically
    within the KPRIET campus geo-fencing perimeter.
    """
    config = get_current_system_config(db)
    result = validate_geofence(
        student_lat=payload.latitude,
        student_lon=payload.longitude,
        campus_lat=config.campus_latitude,
        campus_lon=config.campus_longitude,
        allowed_radius_meters=config.geofence_radius_meters,
        is_mock=payload.is_mock
    )

    if not result["valid"]:
        return LocationVerifyResponse(
            inside_geofence=False,
            distance_meters=-1.0,
            radius_meters=config.geofence_radius_meters,
            campus_name=config.campus_name,
            message=result["reason"]
        )

    inside = result["inside"]
    distance = result["distance"]

    message = (
        f"You are inside the {config.campus_name} campus ({distance:.1f}m from center)."
        if inside
        else f"You are outside the college campus ({distance:.1f}m away, permitted: {config.geofence_radius_meters:.0f}m). Attendance cannot be registered."
    )

    return LocationVerifyResponse(
        inside_geofence=inside,
        distance_meters=distance,
        radius_meters=config.geofence_radius_meters,
        campus_name=config.campus_name,
        message=message
    )

@router.post("/start-verification", response_model=StartVerificationResponse)
def start_verification(
    current_user: dict = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Step 2: Generate a cryptographically random, short-lived verification session
    and assign a randomized liveness challenge (Blink twice, turn head, etc.).
    """
    student_id = int(current_user["sub"])
    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    
    if not student.facial_embedding:
        raise HTTPException(status_code=400, detail="No registered facial profile found. Please contact hostel staff.")

    challenge_type, challenge_prompt = get_random_challenge()
    
    # Invalidate previous unused sessions for this student
    db.query(VerificationSession).filter(
        VerificationSession.student_id == student.id,
        VerificationSession.is_used == False
    ).delete()

    session_token = secrets.token_hex(32)
    now_dt = datetime.datetime.utcnow()
    expires_at = now_dt + datetime.timedelta(seconds=90) # 90-second lifespan

    session = VerificationSession(
        session_token=session_token,
        student_id=student.id,
        challenge_type=challenge_type,
        challenge_prompt=challenge_prompt,
        created_at=now_dt,
        expires_at=expires_at,
        is_used=False,
        liveness_verified=False,
        face_verified=False,
        similarity_score=0.0
    )
    db.add(session)
    db.commit()

    return StartVerificationResponse(
        session_token=session_token,
        challenge_type=challenge_type,
        challenge_prompt=challenge_prompt,
        expires_in_seconds=90
    )

@router.post("/verify-face", response_model=VerifyFaceResponse)
def verify_face_challenge(
    payload: VerifyFaceRequest,
    current_user: dict = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Step 3: Verify the student's live camera frame against the assigned challenge
    and their registered 128D facial embedding with anti-spoofing checks.
    """
    student_id = int(current_user["sub"])
    session = db.query(VerificationSession).filter(
        VerificationSession.session_token == payload.session_token,
        VerificationSession.student_id == student_id
    ).first()

    if not session:
        raise HTTPException(status_code=400, detail="Invalid verification session token.")

    if session.is_used:
        raise HTTPException(status_code=400, detail="Verification session has already been used. Replay detected.")

    if datetime.datetime.utcnow() > session.expires_at:
        raise HTTPException(status_code=400, detail="Verification session has expired. Please restart face scan.")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or not student.facial_embedding:
        raise HTTPException(status_code=400, detail="Facial embedding profile not found.")

    # Execute challenge-response liveness + anti-spoofing + biometric match
    result = verify_live_face_with_challenge(
        live_image_data=payload.face_image_base64,
        registered_embedding_json=student.facial_embedding,
        expected_challenge=session.challenge_type,
        detected_challenge=payload.challenge_action_detected
    )

    if not result.get("matched") or not result.get("liveness_passed"):
        return VerifyFaceResponse(
            verified=False,
            liveness_passed=result.get("liveness_passed", False),
            similarity_score=result.get("confidence", 0.0),
            message=result.get("message", "Face verification failed.")
        )

    # Mark session as verified
    session.liveness_verified = True
    session.face_verified = True
    session.similarity_score = result["confidence"]
    db.commit()

    return VerifyFaceResponse(
        verified=True,
        liveness_passed=True,
        similarity_score=result["confidence"],
        message="Live face and challenge successfully verified."
    )

@router.post("/mark", response_model=AttendanceResponse)
def mark_verified_attendance(
    payload: MarkAttendanceRequest,
    current_user: dict = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Step 4: Final attendance submission. Requires a valid, unexpired, verified session token.
    Enforces time window (7-8 PM), geofence, and duplicate prevention. Burns the session token.
    """
    student_id = int(current_user["sub"])
    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    # 1. Validate session
    session = db.query(VerificationSession).filter(
        VerificationSession.session_token == payload.session_token,
        VerificationSession.student_id == student.id
    ).first()

    if not session:
        raise HTTPException(status_code=400, detail="Invalid verification session token.")

    if session.is_used:
        raise HTTPException(status_code=400, detail="Verification session has already been submitted. Replay rejected.")

    if datetime.datetime.utcnow() > session.expires_at:
        raise HTTPException(status_code=400, detail="Verification session has expired. Please restart face scan.")

    if not session.liveness_verified or not session.face_verified:
        raise HTTPException(status_code=400, detail="Liveness and facial verification not completed for this session.")

    config = get_current_system_config(db)
    today = get_ist_today()
    now_dt = get_ist_now()

    # 2. Check Time Window (Evaluated strictly in Indian Standard Time - IST)
    check_time = now_dt.time()
    if payload.test_time_override:
        try:
            check_time = parse_time_str(payload.test_time_override)
        except Exception:
            pass

    in_window, time_msg = is_within_attendance_window(config, check_time)
    if not in_window:
        raise HTTPException(status_code=400, detail=f"Attendance registration rejected: {time_msg}")

    # 3. Check for Duplicate Attendance for Today
    existing = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.attendance_date == today
    ).first()

    if existing and existing.status == "PRESENT":
        raise HTTPException(
            status_code=400,
            detail=f"Attendance already registered for today ({today.strftime('%d-%m-%Y')} at {existing.attendance_time.strftime('%I:%M %p')}). Duplicate attendance is not permitted."
        )

    # 4. Check Geofence & Mock Location
    geo_result = validate_geofence(
        student_lat=payload.latitude,
        student_lon=payload.longitude,
        campus_lat=config.campus_latitude,
        campus_lon=config.campus_longitude,
        allowed_radius_meters=config.geofence_radius_meters,
        is_mock=payload.is_mock
    )

    if not geo_result["valid"] or not geo_result["inside"]:
        raise HTTPException(
            status_code=400,
            detail="You are outside the college campus. Attendance cannot be registered."
        )

    # 5. Burn session token to prevent reuse / replay
    session.is_used = True

    # 6. Record Attendance
    if existing:
        existing.attendance_time = now_dt.time()
        existing.timestamp = now_dt
        existing.latitude = payload.latitude
        existing.longitude = payload.longitude
        existing.distance_from_campus = geo_result["distance"]
        existing.face_confidence = session.similarity_score
        existing.liveness_passed = True
        existing.status = "PRESENT"
        existing.remarks = f"Verified via live camera & challenge ({session.challenge_type})"
        record = existing
    else:
        record = Attendance(
            student_id=student.id,
            attendance_date=today,
            attendance_time=now_dt.time(),
            timestamp=now_dt,
            latitude=payload.latitude,
            longitude=payload.longitude,
            distance_from_campus=geo_result["distance"],
            face_confidence=session.similarity_score,
            liveness_passed=True,
            status="PRESENT",
            remarks=f"Verified via live camera & challenge ({session.challenge_type})"
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    return AttendanceResponse(
        id=record.id,
        student_id=student.id,
        student_name=student.name,
        register_number=student.register_number,
        attendance_date=record.attendance_date,
        attendance_time=record.attendance_time.strftime("%I:%M %p"),
        status=record.status,
        distance_from_campus=record.distance_from_campus,
        face_confidence=record.face_confidence,
        message="Attendance Successfully Registered!"
    )


@router.post("/submit", response_model=AttendanceResponse)
def submit_attendance(
    payload: AttendanceSubmission,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Full Facial Recognition & Geofenced Attendance Registration:
    - Verifies time window (7:00 PM - 8:00 PM)
    - Verifies GPS physical presence inside KPRIET campus boundary
    - Verifies duplicate attendance prevention
    - Verifies face match with registered profile
    - Verifies active liveness
    """
    # 1. Determine student ID
    if current_user.get("role") == "student":
        student_id = int(current_user["sub"])
    elif payload.student_id:
        student_id = payload.student_id
    else:
        raise HTTPException(status_code=400, detail="Student ID missing.")

    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found or deactivated.")

    config = get_current_system_config(db)
    today = get_ist_today()
    now_dt = get_ist_now()

    # 2. Check Time Window (Evaluated strictly in Indian Standard Time - IST)
    check_time = now_dt.time()
    if payload.test_time_override:
        try:
            check_time = parse_time_str(payload.test_time_override)
        except Exception:
            pass

    in_window, time_msg = is_within_attendance_window(config, check_time)
    if not in_window:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attendance registration rejected: {time_msg}"
        )

    # 3. Check for Duplicate Attendance for Today
    existing = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.attendance_date == today
    ).first()

    if existing and existing.status == "PRESENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attendance already registered for today ({today.strftime('%d-%m-%Y')} at {existing.attendance_time.strftime('%I:%M %p')}). Duplicate attendance is not permitted."
        )

    # 4. Check Geofence & Mock Location
    geo_result = validate_geofence(
        student_lat=payload.latitude,
        student_lon=payload.longitude,
        campus_lat=config.campus_latitude,
        campus_lon=config.campus_longitude,
        allowed_radius_meters=config.geofence_radius_meters,
        is_mock=payload.is_mock
    )

    if not geo_result["valid"] or not geo_result["inside"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are outside the college campus. Attendance cannot be registered."
        )

    # 5. Facial Recognition & Liveness Verification
    if not student.facial_embedding:
        raise HTTPException(status_code=400, detail="Student has not registered a facial profile. Please contact hostel staff.")

    face_result = verify_live_face(
        live_image_data=payload.face_image_base64,
        registered_embedding_json=student.facial_embedding
    )

    if not face_result.get("matched"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Face verification failed. Please try again. ({face_result.get('message')})"
        )

    # 6. Record Attendance
    if existing:
        existing.attendance_time = now_dt.time()
        existing.timestamp = now_dt
        existing.latitude = payload.latitude
        existing.longitude = payload.longitude
        existing.distance_from_campus = geo_result["distance"]
        existing.face_confidence = face_result["confidence"]
        existing.liveness_passed = face_result.get("liveness_passed", True)
        existing.status = "PRESENT"
        existing.remarks = "Verified via facial recognition & geofencing"
        record = existing
    else:
        record = Attendance(
            student_id=student.id,
            attendance_date=today,
            attendance_time=now_dt.time(),
            timestamp=now_dt,
            latitude=payload.latitude,
            longitude=payload.longitude,
            distance_from_campus=geo_result["distance"],
            face_confidence=face_result["confidence"],
            liveness_passed=face_result.get("liveness_passed", True),
            status="PRESENT",
            remarks="Verified via facial recognition & geofencing",
            mock_detected=payload.is_mock
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    return AttendanceResponse(
        id=record.id,
        student_id=student.id,
        student_name=student.name,
        register_number=student.register_number,
        attendance_date=record.attendance_date,
        attendance_time=record.attendance_time.strftime("%I:%M %p"),
        status=record.status,
        distance_from_campus=record.distance_from_campus,
        face_confidence=record.face_confidence,
        message="Attendance Successfully Registered!"
    )

@router.get("/dashboard/student", response_model=StudentDashboardResponse)
def get_student_dashboard(
    current_user: dict = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Returns student dashboard metrics:
    - Welcome banner
    - Today's status (PRESENT / PENDING / ABSENT)
    - Attendance percentage
    - Total present & absent counts
    - Recent attendance logs
    - Monthly distribution
    """
    student_id = int(current_user["sub"])
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    config = get_current_system_config(db)
    now_dt = get_ist_now()
    now_time = now_dt.time()
    in_window, _ = is_within_attendance_window(config, now_time)

    today_status, today_time = get_today_student_status(db, student.id, now_dt.date())
    stats = calculate_student_stats(db, student.id)

    # Recent history (last 10 records)
    records = db.query(Attendance).filter(
        Attendance.student_id == student.id
    ).order_by(desc(Attendance.attendance_date)).limit(10).all()

    recent_items = [
        AttendanceRecordItem(
            id=r.id,
            student_id=student.id,
            student_name=student.name,
            register_number=student.register_number,
            department=student.department,
            hostel_room=f"{student.hostel_block} {student.room_number}",
            attendance_date=r.attendance_date,
            attendance_time=r.attendance_time.strftime("%I:%M %p"),
            latitude=r.latitude,
            longitude=r.longitude,
            distance_meters=r.distance_from_campus,
            face_confidence=r.face_confidence,
            status=r.status,
            remarks=r.remarks
        ) for r in records
    ]

    return StudentDashboardResponse(
        student_id=student.id,
        name=student.name,
        register_number=student.register_number,
        department=student.department,
        hostel_room=f"{student.hostel_block} - {student.room_number}",
        profile_photo_url=student.profile_photo_url,
        today_status=today_status,
        today_attendance_time=today_time,
        is_window_open=in_window,
        window_start=config.attendance_start_time,
        window_end=config.attendance_end_time,
        current_server_time=now_time.strftime("%I:%M %p"),
        total_present_days=stats["present_count"],
        total_absent_days=stats["absent_count"],
        total_applicable_days=stats["applicable_days"],
        attendance_percentage=stats["percentage"],
        recent_history=recent_items,
        monthly_summary=stats["monthly_stats"]
    )

@router.get("/dashboard/staff", response_model=StaffDashboardResponse)
def get_staff_dashboard(
    status_filter: Optional[str] = Query(None, description="PRESENT, ABSENT, PENDING, or ALL"),
    department: Optional[str] = Query(None),
    academic_year: Optional[int] = Query(None),
    query: Optional[str] = Query(None),
    target_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Staff dashboard:
    - Total Registered Students
    - Present Today
    - Absent Today (classified after 8:00 PM)
    - Pending Today (classified before/during 7-8 PM window)
    - Filterable and searchable attendance table
    """
    config = get_current_system_config(db)
    now_dt = get_ist_now()
    now_time = now_dt.time()
    in_window, _ = is_within_attendance_window(config, now_time)

    day = datetime.datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else now_dt.date()
    summary = get_staff_today_summary(db, day)

    # Fetch active students
    q_students = db.query(Student).filter(Student.is_active == True)
    if department and department != "All":
        q_students = q_students.filter(Student.department == department)
    if academic_year:
        q_students = q_students.filter(Student.academic_year == academic_year)
    if query:
        pattern = f"%{query.strip()}%"
        q_students = q_students.filter(
            or_(
                Student.name.ilike(pattern),
                Student.register_number.ilike(pattern)
            )
        )

    students = q_students.order_by(Student.register_number).all()
    student_ids = [s.id for s in students]

    # Fetch attendance for these students on the given day
    attendances = db.query(Attendance).filter(
        Attendance.attendance_date == day,
        Attendance.student_id.in_(student_ids) if student_ids else False
    ).all()

    att_map = {a.student_id: a for a in attendances}
    table_items = []

    for s in students:
        rec = att_map.get(s.id)
        if rec:
            item_status = rec.status
            att_time = rec.attendance_time.strftime("%I:%M %p")
            lat = rec.latitude
            lon = rec.longitude
            dist = rec.distance_from_campus
            conf = rec.face_confidence
            remarks = rec.remarks
            rec_id = rec.id
        else:
            item_status = "ABSENT" if summary["window_closed"] else "PENDING"
            att_time = "-"
            lat = 0.0
            lon = 0.0
            dist = 0.0
            conf = 0.0
            remarks = "No attendance registered"
            rec_id = 0

        # Apply status filter
        if status_filter and status_filter.upper() != "ALL":
            if item_status != status_filter.upper():
                continue

        table_items.append(
            AttendanceRecordItem(
                id=rec_id,
                student_id=s.id,
                student_name=s.name,
                register_number=s.register_number,
                department=s.department,
                hostel_room=f"{s.hostel_block} {s.room_number}",
                attendance_date=day,
                attendance_time=att_time,
                latitude=lat,
                longitude=lon,
                distance_meters=dist,
                face_confidence=conf,
                status=item_status,
                remarks=remarks
            )
        )

    return StaffDashboardResponse(
        total_students=summary["total_students"],
        present_today=summary["present_today"],
        absent_today=summary["absent_today"],
        pending_today=summary["pending_today"],
        attendance_window_open=in_window,
        window_start=config.attendance_start_time,
        window_end=config.attendance_end_time,
        server_time=now_time.strftime("%I:%M %p"),
        records=table_items
    )

@router.get("/absentees", response_model=List[AbsentStudentItem])
def get_absent_students(
    target_date: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Returns list of students who have not marked attendance for the specified date.
    Shows pending before window closes, absent after window closes.
    """
    now_dt = get_ist_now()
    day = datetime.datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else now_dt.date()
    config = get_current_system_config(db)
    now_time = now_dt.time()
    start_time = parse_time_str(config.attendance_start_time)
    end_time = parse_time_str(config.attendance_end_time)

    if start_time <= end_time:
        window_closed = now_time > end_time
    else:
        window_closed = (end_time < now_time < start_time)

    present_ids = [
        row[0] for row in db.query(Attendance.student_id).filter(
            Attendance.attendance_date == day,
            Attendance.status == "PRESENT"
        ).all()
    ]

    q = db.query(Student).filter(
        Student.is_active == True,
        ~Student.id.in_(present_ids) if present_ids else True
    )

    if department and department != "All":
        q = q.filter(Student.department == department)

    absent_students = q.order_by(Student.register_number).all()

    return [
        AbsentStudentItem(
            student_id=s.id,
            name=s.name,
            register_number=s.register_number,
            department=s.department,
            academic_year=s.academic_year,
            hostel_block=s.hostel_block,
            room_number=s.room_number,
            phone_number=s.phone_number,
            profile_photo_url=s.profile_photo_url,
            status="ABSENT" if window_closed else "PENDING"
        ) for s in absent_students
    ]

@router.get("/history", response_model=List[AttendanceRecordItem])
def get_attendance_history(
    student_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns attendance history records.
    - Students can only view their own records.
    - Staff can filter by student, date range, and department.
    """
    if current_user.get("role") == "student":
        student_id = int(current_user["sub"])

    q = db.query(Attendance, Student).join(Student, Attendance.student_id == Student.id)

    if student_id:
        q = q.filter(Attendance.student_id == student_id)

    if department and department != "All":
        q = q.filter(Student.department == department)

    if start_date:
        s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        q = q.filter(Attendance.attendance_date >= s_date)

    if end_date:
        e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        q = q.filter(Attendance.attendance_date <= e_date)

    results = q.order_by(desc(Attendance.attendance_date), desc(Attendance.attendance_time)).limit(200).all()

    items = []
    for att, st in results:
        items.append(
            AttendanceRecordItem(
                id=att.id,
                student_id=st.id,
                student_name=st.name,
                register_number=st.register_number,
                department=st.department,
                hostel_room=f"{st.hostel_block} {st.room_number}",
                attendance_date=att.attendance_date,
                attendance_time=att.attendance_time.strftime("%I:%M %p"),
                latitude=att.latitude,
                longitude=att.longitude,
                distance_meters=att.distance_from_campus,
                face_confidence=att.face_confidence,
                status=att.status,
                remarks=att.remarks
            )
        )

    return items
