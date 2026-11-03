import json
import base64
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Student, Attendance
from ..schemas import StudentCreate, StudentUpdate, StudentResponse
from ..security import require_staff, hash_password
from ..services.face_service import process_face_registration
from ..services.attendance_service import calculate_student_stats
from ..services.storage_service import save_profile_photo, delete_profile_photo

router = APIRouter(prefix="/api/students", tags=["Student Management"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "profiles")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("", response_model=List[StudentResponse])
def list_students(
    query: Optional[str] = Query(None, description="Search by name or register number"),
    department: Optional[str] = Query(None),
    academic_year: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    List students with search and department/year filters. Restricted to staff/admin.
    """
    q = db.query(Student)

    if query:
        search_pattern = f"%{query.strip()}%"
        q = q.filter(
            or_(
                Student.name.ilike(search_pattern),
                Student.register_number.ilike(search_pattern),
                Student.student_id.ilike(search_pattern)
            )
        )

    if department and department != "All":
        q = q.filter(Student.department == department)

    if academic_year:
        q = q.filter(Student.academic_year == academic_year)

    if is_active is not None:
        q = q.filter(Student.is_active == is_active)

    students = q.order_by(Student.register_number).all()
    return students

@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def add_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Register new student with photograph and facial recognition profile.
    Checks uniqueness of student_id, register_number, and email.
    Generates 128D facial embedding.
    """
    # 1. Uniqueness checks and defaults
    reg_no = payload.register_number.strip()
    st_id = payload.student_id.strip() if payload.student_id else f"KPR{reg_no}"
    st_email = payload.email.strip().lower() if payload.email else f"{reg_no}@kpriet.ac.in"

    if db.query(Student).filter(Student.register_number == reg_no).first():
        raise HTTPException(status_code=400, detail=f"Student with Register Number {reg_no} already exists.")

    if db.query(Student).filter(Student.student_id == st_id).first():
        raise HTTPException(status_code=400, detail=f"Student ID {st_id} is already registered.")

    if db.query(Student).filter(Student.email == st_email).first():
        raise HTTPException(status_code=400, detail=f"Email {st_email} is already registered.")

    # Validate password created by warden
    if not payload.password or len(payload.password.strip()) < 6:
        raise HTTPException(status_code=400, detail="Initial password must be at least 6 characters.")

    if payload.confirm_password and payload.password.strip() != payload.confirm_password.strip():
        raise HTTPException(status_code=400, detail="Password and Confirm Password do not match.")

    # 2. Facial Recognition Profile Generation
    if not payload.profile_image_base64:
        raise HTTPException(status_code=400, detail="Student profile photograph is required for facial recognition registration.")

    face_result = process_face_registration(payload.profile_image_base64)
    if not face_result.get("success"):
        raise HTTPException(status_code=400, detail=f"Facial enrollment failed: {face_result.get('message')}")

    embedding_json = json.dumps(face_result["embedding"])

    # 3. Save profile image to persistent storage (Supabase in production, local/cloud in dev)
    photo_url = save_profile_photo(reg_no, payload.profile_image_base64)
    if not photo_url and os.getenv("ENVIRONMENT", "development").strip().lower() in ("production", "prod"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely upload student photograph to persistent cloud storage. Registration halted."
        )

    # 4. Create Student Record with warden-defined password
    new_student = Student(
        student_id=st_id,
        register_number=reg_no,
        name=payload.name.strip(),
        email=st_email,
        password_hash=hash_password(payload.password.strip()),
        department=payload.department.strip(),
        academic_year=payload.academic_year,
        hostel_block=payload.hostel_block.strip(),
        room_number=payload.room_number.strip(),
        phone_number=payload.phone_number,
        profile_photo_url=photo_url,
        facial_embedding=embedding_json,
        is_active=True
    )

    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return new_student

@router.get("/{student_id}")
def get_student_detail(
    student_id: int,
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Get detailed student information along with attendance statistics.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    stats = calculate_student_stats(db, student.id)

    return {
        "student": StudentResponse.from_orm(student),
        "statistics": stats
    }

@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Update student profile details or re-register facial recognition photo.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if payload.name is not None:
        student.name = payload.name.strip()
    if payload.department is not None:
        student.department = payload.department.strip()
    if payload.academic_year is not None:
        student.academic_year = payload.academic_year
    if payload.hostel_block is not None:
        student.hostel_block = payload.hostel_block.strip()
    if payload.room_number is not None:
        student.room_number = payload.room_number.strip()
    if payload.phone_number is not None:
        student.phone_number = payload.phone_number
    if payload.is_active is not None:
        student.is_active = payload.is_active
    if payload.password:
        student.password_hash = hash_password(payload.password.strip())

    if payload.profile_image_base64:
        face_result = process_face_registration(payload.profile_image_base64)
        if not face_result.get("success"):
            raise HTTPException(status_code=400, detail=f"Facial re-enrollment failed: {face_result.get('message')}")
        student.facial_embedding = json.dumps(face_result["embedding"])

        # Update profile photograph in persistent storage
        photo_url = save_profile_photo(student.register_number, payload.profile_image_base64)
        if photo_url:
            student.profile_photo_url = photo_url
        elif os.getenv("ENVIRONMENT", "development").strip().lower() in ("production", "prod"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update student photograph in cloud storage."
            )

    db.commit()
    db.refresh(student)
    return student

@router.delete("/{student_id}")
def delete_student_permanently(
    student_id: int,
    confirm_register_number: str = Query(..., description="Must match the student's register number exactly"),
    db: Session = Depends(get_db),
    current_staff: dict = Depends(require_staff)
):
    """
    Permanently delete student account, credentials, and biometric profiles.
    Anonymizes historical attendance records for institutional compliance.
    Records administrative audit log.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if confirm_register_number.strip() != student.register_number.strip():
        raise HTTPException(
            status_code=400,
            detail=f"Register number confirmation mismatch. Expected '{student.register_number}', received '{confirm_register_number}'."
        )

    reg_no = student.register_number
    st_name = student.name
    dept = student.department
    year = student.academic_year

    # 1. Purge physical biometric photo files from disk and cloud storage
    if student.profile_photo_url:
        try:
            delete_profile_photo(student.profile_photo_url)
        except Exception:
            pass

    # 2. Delete active verification sessions
    from ..models import VerificationSession, AdminAuditLog
    db.query(VerificationSession).filter(VerificationSession.student_id == student.id).delete()

    # 3. Anonymize historical attendance records
    att_count = db.query(Attendance).filter(Attendance.student_id == student.id).update({
        "student_id": None,
        "is_anonymized": True,
        "anonymized_department": dept,
        "anonymized_academic_year": year
    })

    # 4. Record audit log
    audit = AdminAuditLog(
        performed_by_id=int(current_staff["sub"]),
        performed_by_name=current_staff.get("name", "Authorized Staff"),
        action="PERMANENT_DELETE_STUDENT",
        target_identifier=reg_no,
        details=f"Permanently deleted student {st_name} ({reg_no}). Anonymized {att_count} historical attendance records and purged biometric assets."
    )
    db.add(audit)

    # 5. Delete student record
    db.delete(student)
    db.commit()

    return {
        "success": True,
        "message": "Student has been permanently deleted.",
        "deleted_register_number": reg_no
    }

@router.post("/{student_id}/reset-password")
def reset_student_password(
    student_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_staff: dict = Depends(require_staff)
):
    """
    Allow warden/admin to reset student password.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    new_pwd = payload.get("new_password", "").strip()
    if len(new_pwd) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    student.password_hash = hash_password(new_pwd)
    from ..models import AdminAuditLog
    audit = AdminAuditLog(
        performed_by_id=int(current_staff["sub"]),
        performed_by_name=current_staff.get("name", "Authorized Staff"),
        action="RESET_STUDENT_PASSWORD",
        target_identifier=student.register_number,
        details=f"Reset password for student {student.name} ({student.register_number})."
    )
    db.add(audit)
    db.commit()

    return {"success": True, "message": f"Password reset successfully for student {student.name}."}

