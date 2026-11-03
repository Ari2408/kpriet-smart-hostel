from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Staff, Student
from ..schemas import LoginRequest, TokenResponse, ChangePasswordRequest
from ..security import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Unified login endpoint for both Students and Staff/Warden.
    - Students use their Register Number (e.g. 711321104001) or institutional email.
    - Staff members use their Staff ID or Email (e.g. staff@kpriet.ac.in).
    """
    identifier = request.username.strip()

    # 1. Try Staff lookup first if role_hint is staff or check staff table
    if request.role_hint != "student":
        staff = db.query(Staff).filter(
            (Staff.email == identifier) | (Staff.staff_id == identifier)
        ).first()

        if staff:
            if not staff.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff account is deactivated.")
            if verify_password(request.password, staff.password_hash):
                token = create_access_token({
                    "sub": str(staff.id),
                    "role": staff.role,
                    "name": staff.name,
                    "email": staff.email,
                    "identifier": staff.staff_id
                })
                return TokenResponse(
                    access_token=token,
                    role=staff.role,
                    user_id=staff.id,
                    name=staff.name,
                    identifier=staff.staff_id,
                    department="Administration / Hostel",
                    profile_photo_url=None
                )

    # 2. Try Student lookup
    student = db.query(Student).filter(
        (Student.register_number == identifier) | (Student.email == identifier) | (Student.student_id == identifier)
    ).first()

    if student:
        if not student.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student account is deactivated.")
        if verify_password(request.password, student.password_hash):
            token = create_access_token({
                "sub": str(student.id),
                "role": "student",
                "name": student.name,
                "email": student.email,
                "identifier": student.register_number,
                "department": student.department
            })
            return TokenResponse(
                access_token=token,
                role="student",
                user_id=student.id,
                name=student.name,
                identifier=student.register_number,
                department=student.department,
                profile_photo_url=student.profile_photo_url
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials. Please verify your Register Number / Staff ID and password."
    )

@router.get("/me")
def get_profile(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns authenticated user profile details.
    """
    user_id = int(current_user["sub"])
    role = current_user.get("role")

    if role == "student":
        student = db.query(Student).filter(Student.id == user_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        return {
            "id": student.id,
            "student_id": student.student_id,
            "register_number": student.register_number,
            "name": student.name,
            "email": student.email,
            "department": student.department,
            "academic_year": student.academic_year,
            "hostel_block": student.hostel_block,
            "room_number": student.room_number,
            "phone_number": student.phone_number,
            "profile_photo_url": student.profile_photo_url,
            "role": "student"
        }
    else:
        staff = db.query(Staff).filter(Staff.id == user_id).first()
        if not staff:
            raise HTTPException(status_code=404, detail="Staff profile not found")
        return {
            "id": staff.id,
            "staff_id": staff.staff_id,
            "name": staff.name,
            "email": staff.email,
            "role": staff.role
        }

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allow authenticated student or staff to update their login password.
    """
    from ..security import hash_password
    user_id = int(current_user["sub"])
    role = current_user.get("role")

    if role == "student":
        user = db.query(Student).filter(Student.id == user_id).first()
    else:
        user = db.query(Staff).filter(Staff.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User profile not found.")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    if len(payload.new_password.strip()) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    user.password_hash = hash_password(payload.new_password.strip())
    db.commit()

    return {"success": True, "message": "Password changed successfully."}

