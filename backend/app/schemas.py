from typing import Optional, List
from datetime import date, time, datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    name: str
    identifier: str # register_number or email
    department: Optional[str] = None
    profile_photo_url: Optional[str] = None

class LoginRequest(BaseModel):
    username: str # register_number or email
    password: str
    role_hint: Optional[str] = None # "student" or "staff"

class SystemConfigSchema(BaseModel):
    id: Optional[int] = None
    campus_name: str
    campus_latitude: float
    campus_longitude: float
    geofence_radius_meters: float
    attendance_start_time: str
    attendance_end_time: str
    liveness_strictness: float = 0.65
    is_window_open: Optional[bool] = None
    current_time_ist: Optional[str] = None
    server_timezone: Optional[str] = "Asia/Kolkata (IST)"

class SystemConfigUpdate(BaseModel):
    campus_name: Optional[str] = None
    campus_latitude: Optional[float] = None
    campus_longitude: Optional[float] = None
    geofence_radius_meters: Optional[float] = None
    attendance_start_time: Optional[str] = None
    attendance_end_time: Optional[str] = None
    liveness_strictness: Optional[float] = None

class StudentBase(BaseModel):
    student_id: Optional[str] = None
    register_number: str
    name: str
    email: Optional[EmailStr] = None
    department: str
    academic_year: int
    hostel_block: str
    room_number: str
    phone_number: Optional[str] = None

class StudentCreate(StudentBase):
    password: str
    confirm_password: Optional[str] = None
    profile_image_base64: Optional[str] = None # Base64 enrollment portrait

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ResetPasswordRequest(BaseModel):
    new_password: str

class DeleteStudentRequest(BaseModel):
    confirm_register_number: str

class StartVerificationResponse(BaseModel):
    session_token: str
    challenge_type: str
    challenge_prompt: str
    expires_in_seconds: int

class VerifyFaceRequest(BaseModel):
    session_token: str
    face_image_base64: str
    challenge_action_detected: str
    liveness_metrics: Optional[dict] = None

class VerifyFaceResponse(BaseModel):
    verified: bool
    liveness_passed: bool
    similarity_score: float
    message: str

class MarkAttendanceRequest(BaseModel):
    session_token: str
    latitude: float
    longitude: float
    is_mock: bool = False
    test_time_override: Optional[str] = None

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    academic_year: Optional[int] = None
    hostel_block: Optional[str] = None
    room_number: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    profile_image_base64: Optional[str] = None

class StudentResponse(StudentBase):
    id: int
    profile_photo_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    has_face_enrolled: bool = True

    model_config = ConfigDict(from_attributes=True)

class LocationVerifyRequest(BaseModel):
    latitude: float
    longitude: float
    is_mock: bool = False

class LocationVerifyResponse(BaseModel):
    inside_geofence: bool
    distance_meters: float
    radius_meters: float
    campus_name: str
    message: str

class AttendanceSubmission(BaseModel):
    student_id: Optional[int] = None # Inferred from JWT if student
    latitude: float
    longitude: float
    is_mock: bool = False
    face_image_base64: str
    liveness_challenge_response: Optional[str] = "passed"
    test_time_override: Optional[str] = None # For testing time edge cases

class AttendanceResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    register_number: str
    attendance_date: date
    attendance_time: str
    status: str
    distance_from_campus: float
    face_confidence: float
    message: str

class AttendanceRecordItem(BaseModel):
    id: int
    student_id: int
    student_name: str
    register_number: str
    department: str
    hostel_room: str
    attendance_date: date
    attendance_time: str
    latitude: float
    longitude: float
    distance_meters: float
    face_confidence: float
    status: str
    remarks: Optional[str] = None

class StudentDashboardResponse(BaseModel):
    student_id: int
    name: str
    register_number: str
    department: str
    hostel_room: str
    profile_photo_url: Optional[str] = None
    today_status: str # "PRESENT", "ABSENT", "PENDING", "WINDOW_CLOSED"
    today_attendance_time: Optional[str] = None
    is_window_open: bool
    window_start: str
    window_end: str
    current_server_time: str
    total_present_days: int
    total_absent_days: int
    total_applicable_days: int
    attendance_percentage: float
    recent_history: List[AttendanceRecordItem]
    monthly_summary: dict

class StaffDashboardResponse(BaseModel):
    total_students: int
    present_today: int
    absent_today: int
    pending_today: int
    attendance_window_open: bool
    window_start: str
    window_end: str
    server_time: str
    records: List[AttendanceRecordItem]

class AbsentStudentItem(BaseModel):
    student_id: int
    name: str
    register_number: str
    department: str
    academic_year: int
    hostel_block: str
    room_number: str
    phone_number: Optional[str] = None
    profile_photo_url: Optional[str] = None
    status: str
