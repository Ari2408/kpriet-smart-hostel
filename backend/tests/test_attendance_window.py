#!/usr/bin/env python3
"""
test_attendance_window.py - Unit and Integration Tests for Attendance Window Synchronization & IST Validation

Validates:
1. Standard same-day window checks (e.g., 19:00–21:00 IST)
2. Overnight/midnight-crossing window checks (e.g., 22:00–02:00 IST)
3. Strict boundary conditions (before start, exact start, inside, exact end, after end)
4. Informative rejection error messages matching institutional requirements
5. Time string normalization and validation
6. Timezone portability: UTC server time vs. Indian Standard Time (IST)
"""

import sys
import os
import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure self-contained local SQLite execution for tests
os.environ["DATABASE_URL"] = f"sqlite:///{(BACKEND_DIR / 'smart_hostel.db').as_posix()}"
os.environ["ENVIRONMENT"] = "development"

from app.models import SystemConfig
from app.services.attendance_service import (
    is_within_attendance_window,
    parse_time_str,
    get_ist_now,
    get_ist_today,
    get_ist_time,
    IST
)
from app.routers.config import _normalize_time_str
from fastapi import HTTPException

def test_parse_time_str():
    print("Testing parse_time_str()...")
    t1 = parse_time_str("19:00")
    assert t1 == datetime.time(19, 0, 0), f"Expected 19:00:00, got {t1}"
    
    t2 = parse_time_str("07:30:00")
    assert t2 == datetime.time(7, 30, 0), f"Expected 07:30:00, got {t2}"

    t3 = parse_time_str("  23:59  ")
    assert t3 == datetime.time(23, 59, 0), f"Expected 23:59:00, got {t3}"
    print("  -> Passed parse_time_str().")

def test_normalize_time_str():
    print("Testing _normalize_time_str()...")
    assert _normalize_time_str("19:00", "Start") == "19:00"
    assert _normalize_time_str("7:05", "Start") == "07:05"
    assert _normalize_time_str("00:00", "Start") == "00:00"
    assert _normalize_time_str("23:59", "Start") == "23:59"

    # Test invalid inputs
    invalid_cases = ["24:00", "12:60", "7pm", "19-00", "abc", ""]
    for inv in invalid_cases:
        try:
            _normalize_time_str(inv, "Test field")
            assert False, f"Expected HTTPException for invalid time '{inv}'"
        except HTTPException as exc:
            assert exc.status_code == 400
    print("  -> Passed _normalize_time_str().")

def test_standard_same_day_window():
    print("Testing standard same-day window (19:00 - 21:00 IST)...")
    config = SystemConfig(
        attendance_start_time="19:00",
        attendance_end_time="21:00"
    )

    # 1. Before opening (18:59)
    in_win, msg = is_within_attendance_window(config, datetime.time(18, 59))
    assert not in_win, "18:59 should be rejected"
    assert "not opened yet" in msg
    assert "19:00–21:00 IST" in msg
    assert "18:59 IST" in msg

    # 2. Exact start (19:00)
    in_win, msg = is_within_attendance_window(config, datetime.time(19, 0))
    assert in_win, "19:00 should be allowed"
    assert "Within allowed attendance window" in msg

    # 3. Inside window (20:00)
    in_win, msg = is_within_attendance_window(config, datetime.time(20, 0))
    assert in_win, "20:00 should be allowed"
    assert "Within allowed attendance window" in msg

    # 4. Exact end (21:00)
    in_win, msg = is_within_attendance_window(config, datetime.time(21, 0))
    assert in_win, "21:00 should be allowed"
    assert "Within allowed attendance window" in msg

    # 5. After closing (21:01)
    in_win, msg = is_within_attendance_window(config, datetime.time(21, 1))
    assert not in_win, "21:01 should be rejected"
    assert "closed" in msg
    assert "19:00–21:00 IST" in msg
    assert "21:01 IST" in msg

    print("  -> Passed standard same-day window tests.")

def test_midnight_spanning_window():
    print("Testing midnight-spanning window (22:00 - 02:00 IST)...")
    config = SystemConfig(
        attendance_start_time="22:00",
        attendance_end_time="02:00"
    )

    # 1. Before opening (21:59)
    in_win, msg = is_within_attendance_window(config, datetime.time(21, 59))
    assert not in_win, "21:59 should be rejected"
    assert "closed" in msg or "not opened" in msg

    # 2. Exact start (22:00)
    in_win, msg = is_within_attendance_window(config, datetime.time(22, 0))
    assert in_win, "22:00 should be allowed"

    # 3. Pre-midnight (23:30)
    in_win, msg = is_within_attendance_window(config, datetime.time(23, 30))
    assert in_win, "23:30 should be allowed"

    # 4. Post-midnight (01:15)
    in_win, msg = is_within_attendance_window(config, datetime.time(1, 15))
    assert in_win, "01:15 should be allowed"

    # 5. Exact closing (02:00)
    in_win, msg = is_within_attendance_window(config, datetime.time(2, 0))
    assert in_win, "02:00 should be allowed"

    # 6. After closing (02:01)
    in_win, msg = is_within_attendance_window(config, datetime.time(2, 1))
    assert not in_win, "02:01 should be rejected"

    # 7. Midday (14:00)
    in_win, msg = is_within_attendance_window(config, datetime.time(14, 0))
    assert not in_win, "14:00 should be rejected"

    print("  -> Passed midnight-spanning window tests.")

def test_timezone_conversion():
    print("Testing UTC to IST timezone localization...")
    # Simulate a UTC time on a cloud server: 14:00 UTC = 19:30 IST
    utc_dt = datetime.datetime(2026, 11, 3, 14, 0, 0, tzinfo=datetime.timezone.utc)
    ist_dt = utc_dt.astimezone(IST)

    assert ist_dt.hour == 19 and ist_dt.minute == 30, f"Expected 19:30 IST, got {ist_dt.strftime('%H:%M')}"

    config = SystemConfig(attendance_start_time="19:00", attendance_end_time="20:00")
    in_win, msg = is_within_attendance_window(config, ist_dt.time())
    assert in_win, "14:00 UTC (19:30 IST) MUST be within 19:00 - 20:00 IST window"
    assert "19:30 IST" in msg

    # Also check midnight boundary in UTC: 19:00 UTC = 00:30 IST next day
    utc_night = datetime.datetime(2026, 11, 3, 19, 0, 0, tzinfo=datetime.timezone.utc)
    ist_night = utc_night.astimezone(IST)
    assert ist_night.date() == datetime.date(2026, 11, 4)
    assert ist_night.hour == 0 and ist_night.minute == 30

    print("  -> Passed UTC to IST conversion tests.")

def main():
    print("=" * 80)
    print("  KPRIET SMART HOSTEL - ATTENDANCE WINDOW & IST SYNCHRONIZATION TESTS")
    print("=" * 80)
    test_parse_time_str()
    test_normalize_time_str()
    test_standard_same_day_window()
    test_midnight_spanning_window()
    test_timezone_conversion()
    print("=" * 80)
    print("  ALL ATTENDANCE WINDOW TESTS PASSED SUCCESSFULLY.")
    print("=" * 80)

if __name__ == "__main__":
    main()
