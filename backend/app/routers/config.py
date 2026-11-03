import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SystemConfig
from ..schemas import SystemConfigSchema, SystemConfigUpdate
from ..security import require_staff
from ..services.attendance_service import (
    get_current_system_config,
    get_ist_time,
    is_within_attendance_window
)

router = APIRouter(prefix="/api/config", tags=["System Configuration"])

TIME_FORMAT_REGEX = r"^([01]?\d|2[0-3]):[0-5]\d$"

def _normalize_time_str(time_val: str, field_name: str) -> str:
    cleaned = time_val.strip()
    if not re.match(TIME_FORMAT_REGEX, cleaned):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be in 24-hour HH:MM format (e.g. 19:00, 20:30)."
        )
    parts = cleaned.split(":")
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"

@router.get("", response_model=SystemConfigSchema)
def get_config(db: Session = Depends(get_db)):
    """
    Get current college campus coordinates, radius, and attendance time window.
    Includes active attendance window status evaluated in Indian Standard Time (IST).
    Publicly accessible to mobile app for geofencing pre-checks and window synchronization.
    """
    config = get_current_system_config(db)
    now_time = get_ist_time()
    in_window, _ = is_within_attendance_window(config, now_time)

    return SystemConfigSchema(
        id=config.id,
        campus_name=config.campus_name,
        campus_latitude=config.campus_latitude,
        campus_longitude=config.campus_longitude,
        geofence_radius_meters=config.geofence_radius_meters,
        attendance_start_time=config.attendance_start_time,
        attendance_end_time=config.attendance_end_time,
        liveness_strictness=config.liveness_strictness or 0.65,
        is_window_open=in_window,
        current_time_ist=now_time.strftime("%H:%M"),
        server_timezone="Asia/Kolkata (IST)"
    )

@router.put("", response_model=SystemConfigSchema)
def update_config(
    payload: SystemConfigUpdate,
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Admin endpoint to configure campus geofencing coordinates, radius, and time window.
    Validates 24-hour time format (HH:MM) and synchronizes single source of truth in database.
    """
    config = get_current_system_config(db)

    if payload.campus_name is not None:
        config.campus_name = payload.campus_name.strip()
    if payload.campus_latitude is not None:
        if not (-90.0 <= payload.campus_latitude <= 90.0):
            raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
        config.campus_latitude = payload.campus_latitude
    if payload.campus_longitude is not None:
        if not (-180.0 <= payload.campus_longitude <= 180.0):
            raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
        config.campus_longitude = payload.campus_longitude
    if payload.geofence_radius_meters is not None:
        if payload.geofence_radius_meters <= 0:
            raise HTTPException(status_code=400, detail="Radius must be greater than zero")
        config.geofence_radius_meters = payload.geofence_radius_meters
    if payload.attendance_start_time is not None:
        config.attendance_start_time = _normalize_time_str(payload.attendance_start_time, "Attendance start time")
    if payload.attendance_end_time is not None:
        config.attendance_end_time = _normalize_time_str(payload.attendance_end_time, "Attendance end time")
    if payload.liveness_strictness is not None:
        config.liveness_strictness = payload.liveness_strictness

    db.commit()
    db.refresh(config)

    now_time = get_ist_time()
    in_window, _ = is_within_attendance_window(config, now_time)

    return SystemConfigSchema(
        id=config.id,
        campus_name=config.campus_name,
        campus_latitude=config.campus_latitude,
        campus_longitude=config.campus_longitude,
        geofence_radius_meters=config.geofence_radius_meters,
        attendance_start_time=config.attendance_start_time,
        attendance_end_time=config.attendance_end_time,
        liveness_strictness=config.liveness_strictness,
        is_window_open=in_window,
        current_time_ist=now_time.strftime("%H:%M"),
        server_timezone="Asia/Kolkata (IST)"
    )
