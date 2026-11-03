import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Time, Text, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from .database import Base

class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    campus_name = Column(String(255), default="KPR Institute of Engineering and Technology")
    campus_latitude = Column(Float, default=11.05445, nullable=False) # KPRIET default
    campus_longitude = Column(Float, default=77.08641, nullable=False)
    geofence_radius_meters = Column(Float, default=500.0, nullable=False)
    attendance_start_time = Column(String(10), default="19:00", nullable=False) # 7:00 PM
    attendance_end_time = Column(String(10), default="20:00", nullable=False)   # 8:00 PM
    liveness_strictness = Column(Float, default=0.65)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="staff", nullable=False) # "admin", "warden", "staff"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(50), unique=True, index=True, nullable=False) # e.g. KPR2024CS001
    register_number = Column(String(50), unique=True, index=True, nullable=False) # e.g. 711321104001
    name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False) # e.g. CSE, ECE, AI&DS
    academic_year = Column(Integer, nullable=False) # 1, 2, 3, 4
    hostel_block = Column(String(100), nullable=False) # e.g. Emerald Block
    room_number = Column(String(50), nullable=False) # e.g. B-204
    phone_number = Column(String(30), nullable=True)
    profile_photo_url = Column(String(255), nullable=True)
    facial_embedding = Column(Text, nullable=False) # JSON array of 128 float values
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    attendances = relationship("Attendance", back_populates="student")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    attendance_date = Column(Date, nullable=False, index=True) # YYYY-MM-DD
    attendance_time = Column(Time, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    distance_from_campus = Column(Float, nullable=False)
    face_confidence = Column(Float, nullable=False)
    liveness_passed = Column(Boolean, default=True)
    status = Column(String(20), nullable=False, default="PRESENT") # "PRESENT", "ABSENT", "PENDING"
    remarks = Column(String(255), nullable=True)
    mock_detected = Column(Boolean, default=False)
    
    # Anonymized fields retained after permanent student deletion for institutional audits
    is_anonymized = Column(Boolean, default=False)
    anonymized_department = Column(String(100), nullable=True)
    anonymized_academic_year = Column(Integer, nullable=True)

    student = relationship("Student", back_populates="attendances")

    __table_args__ = (
        Index("idx_attendance_date_status", "attendance_date", "status"),
    )

class VerificationSession(Base):
    __tablename__ = "verification_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String(64), unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_type = Column(String(50), nullable=False) # "BLINK_TWICE", "TURN_HEAD_LEFT", "TURN_HEAD_RIGHT", "LOOK_STRAIGHT"
    challenge_prompt = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    liveness_verified = Column(Boolean, default=False)
    face_verified = Column(Boolean, default=False)
    similarity_score = Column(Float, default=0.0)

class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    performed_by_id = Column(Integer, nullable=False)
    performed_by_name = Column(String(150), nullable=False)
    action = Column(String(50), nullable=False) # e.g. "PERMANENT_DELETE_STUDENT"
    target_identifier = Column(String(100), nullable=False) # e.g. Register Number
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

