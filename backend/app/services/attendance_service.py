import datetime
import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc

from ..models import Attendance, Student, SystemConfig

# Indian Standard Time (IST) is UTC+05:30 with no Daylight Saving Time.
# Using standard datetime.timezone ensures 100% deterministic portability
# across all operating systems (Windows, Linux/Render, Docker, macOS).
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")

def get_ist_now() -> datetime.datetime:
    """Returns current datetime in Indian Standard Time (IST, UTC+5:30)."""
    return datetime.datetime.now(IST)

def get_ist_today() -> datetime.date:
    """Returns current date in Indian Standard Time (IST)."""
    return datetime.datetime.now(IST).date()

def get_ist_time() -> datetime.time:
    """Returns current time of day in Indian Standard Time (IST)."""
    return datetime.datetime.now(IST).time()

def get_current_system_config(db: Session) -> SystemConfig:
    config = db.query(SystemConfig).first()
    if not config:
        config = SystemConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

def parse_time_str(time_str: str) -> datetime.time:
    """
    Parses time strings like '19:00', '19:00:00', or '7:30' into datetime.time.
    """
    parts = [int(p) for p in time_str.strip().split(":")]
    if len(parts) == 2:
        return datetime.time(parts[0], parts[1], 0)
    elif len(parts) >= 3:
        return datetime.time(parts[0], parts[1], parts[2])
    raise ValueError(f"Invalid time format: {time_str}")

def is_within_attendance_window(
    config: SystemConfig,
    check_time: Optional[datetime.time] = None
) -> Tuple[bool, str]:
    """
    Checks whether check_time (or current IST time) is within the allowed attendance window.
    Handles both standard same-day windows (e.g. 19:00 - 23:00) and
    midnight-spanning windows (e.g. 22:00 - 02:00).
    Always evaluates in Indian Standard Time (IST).
    """
    now_time = check_time or get_ist_time()
    start_time = parse_time_str(config.attendance_start_time)
    end_time = parse_time_str(config.attendance_end_time)

    current_ist_str = now_time.strftime("%H:%M")
    window_str = f"{config.attendance_start_time}–{config.attendance_end_time} IST"

    if start_time <= end_time:
        # Standard same-day window (e.g., 19:00 to 21:00)
        if start_time <= now_time <= end_time:
            return True, f"Within allowed attendance window ({window_str}). Current time: {current_ist_str} IST."
        elif now_time < start_time:
            return False, f"Attendance window has not opened yet. Allowed time: {window_str}. Current time: {current_ist_str} IST."
        else:
            return False, f"Attendance window is closed. Allowed time: {window_str}. Current time: {current_ist_str} IST."
    else:
        # Midnight-spanning window (e.g., 22:00 to 02:00 next day)
        if now_time >= start_time or now_time <= end_time:
            return True, f"Within allowed attendance window ({window_str}). Current time: {current_ist_str} IST."
        else:
            return False, f"Attendance window is closed. Allowed time: {window_str}. Current time: {current_ist_str} IST."

def calculate_student_stats(db: Session, student_id: int) -> Dict[str, Any]:
    """
    Computes attendance statistics for a given student:
    - Total present days
    - Total absent days
    - Total applicable days
    - Attendance percentage: (Present / Applicable) * 100
    - Monthly distribution
    """
    present_count = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.status == "PRESENT"
    ).count()

    absent_count = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.status == "ABSENT"
    ).count()

    applicable_days = present_count + absent_count
    percentage = round((present_count / max(1, applicable_days)) * 100.0, 1) if applicable_days > 0 else 100.0

    # Monthly breakdown (last 6 months)
    records = db.query(Attendance).filter(
        Attendance.student_id == student_id
    ).order_by(desc(Attendance.attendance_date)).all()

    monthly_stats = {}
    for rec in records:
        month_key = rec.attendance_date.strftime("%b %Y")
        if month_key not in monthly_stats:
            monthly_stats[month_key] = {"present": 0, "absent": 0, "total": 0}
        
        monthly_stats[month_key]["total"] += 1
        if rec.status == "PRESENT":
            monthly_stats[month_key]["present"] += 1
        elif rec.status == "ABSENT":
            monthly_stats[month_key]["absent"] += 1

    return {
        "present_count": present_count,
        "absent_count": absent_count,
        "applicable_days": applicable_days,
        "percentage": percentage,
        "monthly_stats": monthly_stats
    }

def get_today_student_status(db: Session, student_id: int, today: Optional[datetime.date] = None) -> Tuple[str, Optional[str]]:
    """
    Determines student status for today in IST:
    Returns (status, attendance_time_str)
    """
    target_date = today or get_ist_today()
    record = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.attendance_date == target_date
    ).first()

    if record:
        return record.status, record.attendance_time.strftime("%I:%M %p")

    # If no record exists yet, check window
    config = get_current_system_config(db)
    now_time = get_ist_time()
    start_time = parse_time_str(config.attendance_start_time)
    end_time = parse_time_str(config.attendance_end_time)

    if start_time <= end_time:
        is_past_window = now_time > end_time
    else:
        is_past_window = (end_time < now_time < start_time)

    if is_past_window:
        return "ABSENT", None
    else:
        return "PENDING", None

def get_staff_today_summary(db: Session, target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    Computes dashboard summary for staff in IST:
    - Total registered active students
    - Present today
    - Absent today (only counted after window closes)
    - Pending today (unregistered students during/before window)
    """
    day = target_date or get_ist_today()
    config = get_current_system_config(db)
    now_time = get_ist_time()
    start_time = parse_time_str(config.attendance_start_time)
    end_time = parse_time_str(config.attendance_end_time)

    if start_time <= end_time:
        window_closed = now_time > end_time
    else:
        window_closed = (end_time < now_time < start_time)

    total_active_students = db.query(Student).filter(Student.is_active == True).count()

    present_count = db.query(Attendance).filter(
        Attendance.attendance_date == day,
        Attendance.status == "PRESENT"
    ).count()

    unregistered_count = max(0, total_active_students - present_count)

    if window_closed:
        absent_count = unregistered_count
        pending_count = 0
    else:
        absent_count = 0
        pending_count = unregistered_count

    return {
        "total_students": total_active_students,
        "present_today": present_count,
        "absent_today": absent_count,
        "pending_today": pending_count,
        "window_closed": window_closed
    }
