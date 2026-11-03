# KPRIET Smart Hostel — Attendance Window Synchronization & Flutter UI Overflow Fix Report

**Project**: KPRIET Smart Hostel Attendance Management System  
**Date**: November 3, 2026  
**Backend**: FastAPI (Deployed on Render: `https://kpriet-smart-hostel.onrender.com`)  
**Database**: Supabase PostgreSQL (Managed instance, SSL enabled)  
**Mobile Client**: Flutter Android Application (`smart_hostel_app/`)  

---

## 1. Executive Summary

This report documents the root-cause diagnostics, structural remediations, automated testing, and validation completed for two critical production defects reported during live testing of the KPRIET Smart Hostel application:

1. **Issue 1 — Attendance Window Synchronization Failure**:
   - Staff configured new attendance start/end times in Staff Settings, but the student application continued displaying stale hours (e.g., `"Window opens at 19:00"`), and attendance registration was rejected even when staff and students believed the attendance window was active.
   - **Root Cause**: Render Linux containers execute in Coordinated Universal Time (UTC), whereas hostel operations run strictly on Indian Standard Time (`Asia/Kolkata` / IST, UTC+05:30). When evaluating attendance in the evening at 19:30 IST, server time was evaluated as 14:00 UTC, causing instantaneous rejection. Furthermore, the mobile client never called `fetchConfig()` on initial load, leaving local in-memory configuration unpopulated.
   - **Resolution**: Implemented deterministic, zero-dependency Indian Standard Time (`IST = UTC+05:30`) boundary evaluation across all attendance routes, window validation helpers, and dashboard metrics; added midnight-spanning window support; enforced 24-hour `HH:MM` time format validation; added explicit IST time and window status fields to the configuration schema; and integrated active configuration synchronization on app initialization and dashboard refresh.

2. **Issue 2 — Flutter UI Layout Pixel Overflows**:
   - Yellow-and-black hazard pixel overflow banners appeared on multiple screens, most notably `"BOTTOM OVERFLOWED BY 28 PIXELS"` on the Staff Dashboard metric cards, keyboard obstruction in the "Permanently Delete Student" dialog, and horizontal overflows with long department titles.
   - **Root Cause**: The Staff Dashboard 2-column GridView forced an aggressive `childAspectRatio: 1.45`, restricting vertical cell height to ~117px while the internal components of `MetricCard` totaled 146px. Dialogs containing input fields lacked scrollable viewports, causing soft keyboards to push dialog content beyond the display boundary. Department name rows used unconstrained `Row` children instead of wrapping flex containers.
   - **Resolution**: Refactored `MetricCard` to use adaptive internal scaling (`FittedBox` on numeric metrics, `Flexible` on title/subtitle labels, compact padding); adjusted Staff GridView ratio to `1.2`; wrapped modal alert dialogs in `SingleChildScrollView`; and replaced fixed horizontal rows with `Wrap` and `Expanded(child: Text(..., textAlign: TextAlign.end))` layouts.

---

## 2. Root Cause Analysis

### A. Issue 1: Timezone Disparity & Configuration Caching
| Component | Previous Flawed Implementation | Impact on Production |
| :--- | :--- | :--- |
| **Server Timezone** | Used `datetime.datetime.now().time()` and `datetime.date.today()` | Render runs in UTC. At 19:30 IST, UTC is 14:00. The check `19:00 <= 14:00 <= 20:00` evaluated to `False`, rejecting all student attendance during legitimate evening hours. |
| **Window Boundary Logic** | Evaluated only `start_time <= now_time <= end_time` | Fails completely for overnight attendance windows spanning midnight (e.g. 22:00 to 02:00 IST), where `start_time > end_time`. |
| **Config Fetching in App** | `ConfigProvider.fetchConfig()` was defined but never invoked | `ConfigProvider.config` remained `null` indefinitely. `admin_settings_screen.dart` initialized with hardcoded defaults (`19:00`, `20:00`) instead of current database state. |
| **Client UI Display** | Hardcoded text `"Window: 19:00 - 20:00 (7 PM - 8 PM)"` | Even if backend returned updated hours, the student UI displayed confusing hardcoded time strings. |
| **Time Format Validation** | Missing in `PUT /api/config` | Staff could inadvertently submit arbitrary strings (e.g. `"7pm"`, `"19:00:00"`), triggering unhandled parse exceptions. |

### B. Issue 2: Layout Constraint Overflows
| Screen & Widget | Error Manifestation | Underlying Layout Defect |
| :--- | :--- | :--- |
| **Staff Dashboard (`MetricCard`)** | `A RenderFlex overflowed by 28 pixels on the bottom.` | `GridView.count(crossAxisCount: 2, childAspectRatio: 1.45)` constrained card height to ~117px. With fixed 16px paddings, 26pt font, and icon spacing, intrinsic height was 146px ($146 - 118 = 28$px overflow). |
| **Delete Student Dialog** | Overflowed bottom when virtual keyboard opened | `AlertDialog(content: Column(...))` without a `SingleChildScrollView`. On screens <6-inch or when soft keyboard opened, vertical space collapsed. |
| **Reset Password Dialog** | Overflowed bottom when virtual keyboard opened | `AlertDialog(content: Column(...))` without scroll enclosure. |
| **Student Detail Screen** | Horizontal overflow on long department names | `Row(children: [_chip(department), _chip(academicYear)])`. Long names like "Electronics & Communication Engineering" exceeded display width. |
| **Personal Information Table** | Right-side overflow on email/department | `Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(label), Text(value)])` lacked flex constraints on `value`. |

---

## 3. Remediation Details

### A. Backend Timezone & Window Architecture

#### 1. Centralized IST Definition (`backend/app/services/attendance_service.py`)
```python
# Indian Standard Time (IST) is UTC+05:30 with no Daylight Saving Time.
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
```

#### 2. Robust Window Validation & Informative Diagnostics
```python
def is_within_attendance_window(
    config: SystemConfig,
    check_time: Optional[datetime.time] = None
) -> Tuple[bool, str]:
    now_time = check_time or get_ist_time()
    start_time = parse_time_str(config.attendance_start_time)
    end_time = parse_time_str(config.attendance_end_time)

    current_ist_str = now_time.strftime("%H:%M")
    window_str = f"{config.attendance_start_time}–{config.attendance_end_time} IST"

    if start_time <= end_time:
        # Standard same-day window (e.g. 19:00 to 21:00)
        if start_time <= now_time <= end_time:
            return True, f"Within allowed attendance window ({window_str}). Current time: {current_ist_str} IST."
        elif now_time < start_time:
            return False, f"Attendance window has not opened yet. Allowed time: {window_str}. Current time: {current_ist_str} IST."
        else:
            return False, f"Attendance window is closed. Allowed time: {window_str}. Current time: {current_ist_str} IST."
    else:
        # Midnight-spanning window (e.g. 22:00 to 02:00)
        if now_time >= start_time or now_time <= end_time:
            return True, f"Within allowed attendance window ({window_str}). Current time: {current_ist_str} IST."
        else:
            return False, f"Attendance window is closed. Allowed time: {window_str}. Current time: {current_ist_str} IST."
```

#### 3. Strict 24-Hour Time Format Validation (`backend/app/routers/config.py`)
```python
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
```

#### 4. Extended System Configuration Schema (`backend/app/schemas.py`)
```python
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
```

---

### B. Flutter Mobile Application Remediations

#### 1. Adaptive `MetricCard` Widget (`lib/widgets/metric_card.dart`)
- Changed card padding to `EdgeInsets.symmetric(horizontal: 14, vertical: 12)`.
- Wrapped subtitle in `Flexible(child: Text(subtitle!, maxLines: 1, overflow: TextOverflow.ellipsis))`.
- Wrapped metric value in `Flexible(child: FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(value, ...)))`.
- Applied `maxLines: 1, overflow: TextOverflow.ellipsis` to title labels.

#### 2. Staff Dashboard Grid Resolution (`lib/features/staff/staff_dashboard_screen.dart`)
- Updated `GridView.count` `childAspectRatio` from `1.45` to `1.2`, providing adequate vertical room for metric statistics cards.
- Added explicit IST indicators:
  `"Window: ${data?.windowStart} - ${data?.windowEnd} IST • Server Time: ${data?.serverTime} IST"`
- Triggered `context.read<ConfigProvider>().fetchConfig()` in `initState` and `RefreshIndicator`.

#### 3. Student Dashboard Synchronization (`lib/features/student/student_dashboard_screen.dart`)
- Added `ConfigProvider.fetchConfig()` trigger on `initState` and pull-to-refresh.
- Removed hardcoded `(7 PM - 8 PM)` label; dynamically displays `${data?.windowStart} - ${data?.windowEnd} IST`.
- Added visual status pill: `WINDOW OPEN` (green) or `WINDOW CLOSED` (muted).
- Displays exact server time: `Current Server Time: ${data!.currentServerTime} IST`.
- Replaced blind navigation with an intelligent action button:
  - If open: navigates to `/location-verification`.
  - If closed: displays an informative dialog detailing allowed hours and current IST time.
- Constrained `_infoChip` max width with `ConstrainedBox(constraints: BoxConstraints(maxWidth: 160))` and `TextOverflow.ellipsis`.

#### 4. Admin Settings Form Validation (`lib/features/staff/admin_settings_screen.dart`)
- Added post-frame callback in `initState` to fetch latest configuration from backend and populate controllers.
- Added client-side regex check (`^([01]?\d|2[0-3]):[0-5]\d$`) on start and end time fields before submitting.
- On successful update, immediately triggers `context.read<StaffProvider>().fetchDashboard()`.

#### 5. Keyboard & Text Wrapping in Student Details (`lib/features/staff/student_detail_screen.dart`)
- Enclosed `_showDeleteStudentDialog` content in a `SingleChildScrollView`.
- Enclosed `_showResetPasswordDialog` content in a `SingleChildScrollView`.
- Replaced fixed `Row` of department/year chips with `Wrap(alignment: WrapAlignment.center, spacing: 8, runSpacing: 6)`.
- Refactored `_detailItem(label, value)`:
  ```dart
  Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
      const SizedBox(width: 12),
      Expanded(
        child: Text(
          value,
          textAlign: TextAlign.end,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
        ),
      ),
    ],
  )
  ```

---

## 4. Automated Verification Results

### Test Suite 1: Attendance Window & IST Synchronization (`backend/tests/test_attendance_window.py`)
```
================================================================================
  KPRIET SMART HOSTEL - ATTENDANCE WINDOW & IST SYNCHRONIZATION TESTS
================================================================================
Testing parse_time_str()...
  -> Passed parse_time_str().
Testing _normalize_time_str()...
  -> Passed _normalize_time_str().
Testing standard same-day window (19:00 - 21:00 IST)...
  -> Passed standard same-day window tests.
Testing midnight-spanning window (22:00 - 02:00 IST)...
  -> Passed midnight-spanning window tests.
Testing UTC to IST timezone localization...
  -> Passed UTC to IST conversion tests.
================================================================================
  ALL ATTENDANCE WINDOW TESTS PASSED SUCCESSFULLY.
================================================================================
Result: 5 of 5 tests passed (Exit code: 0)
```

### Test Suite 2: Student Photo Security & Authorization (`backend/tests/test_photo_security.py`)
```
================================================================================
  KPRIET SMART HOSTEL - STUDENT PHOTO ENDPOINT SECURITY TEST SUITE
================================================================================
[1/8] Testing unauthenticated request... -> Passed (401 Unauthorized)
[2/8] Testing authorized staff request... -> Passed (200 OK)
[3/8] Testing student accessing their OWN photo... -> Passed (200 OK)
[4/8] Testing student B attempting to access student A's photo... -> Passed (403 Forbidden)
[5/8] Testing path traversal attacks... -> Passed (400 Bad Request)
[6/8] Testing missing photograph request... -> Passed (404 Not Found)
[7/8] Testing Cache-Control security policy... -> Passed (private, no-cache, no-store)
[8/8] Testing query-parameter token authentication (?token=...)... -> Passed (200 OK)
================================================================================
  ALL 8 SECURITY & AUTHORIZATION TESTS PASSED. ENDPOINT IS FULLY SECURED.
================================================================================
Result: 8 of 8 tests passed (Exit code: 0)
```

### Test Suite 3: Render Production Readiness (`backend/tests/test_render_readiness.py`)
```
Ran 15 tests in 0.161s
OK
================================================================================
  ALL RENDER PRODUCTION READINESS TESTS PASSED!
================================================================================
Result: 15 of 15 tests passed (Exit code: 0)
```

### Test Suite 4: Flutter Static Analysis (`dart analyze smart_hostel_app/lib`)
```
Analyzing lib...
No issues found!
Result: 0 errors, 0 warnings, 0 lints (Exit code: 0)
```

---

## 5. Summary of Modified Files

| File Path | Description of Changes |
| :--- | :--- |
| `backend/app/services/attendance_service.py` | Added `IST` timezone helper functions (`get_ist_now`, `get_ist_today`, `get_ist_time`); updated `is_within_attendance_window`, `get_today_student_status`, `get_staff_today_summary`. |
| `backend/app/schemas.py` | Added `is_window_open`, `current_time_ist`, and `server_timezone` fields to `SystemConfigSchema`. |
| `backend/app/routers/config.py` | Normalized time strings with regex validation; populated IST window status in `get_config` and `update_config`. |
| `backend/app/routers/attendance.py` | Replaced all UTC `datetime.now()` with `get_ist_now()` / `get_ist_today()` across verify-location, start-verification, mark, submit, and dashboard routes. |
| `backend/app/routers/reports.py` | Used `get_ist_today()` for generated CSV and PDF report filenames. |
| `backend/app/database.py` | Added `override=False` to `load_dotenv` to protect test environment overrides. |
| `backend/tests/test_attendance_window.py` | New test suite covering standard windows, overnight windows, boundaries, and IST conversion. |
| `smart_hostel_app/lib/models/system_config_model.dart` | Added `isWindowOpen`, `currentTimeIst`, `serverTimezone` properties and JSON deserialization. |
| `smart_hostel_app/lib/widgets/metric_card.dart` | Added `FittedBox` scaling, `Flexible` labels, and adaptive padding to eliminate 28px bottom overflows. |
| `smart_hostel_app/lib/features/staff/staff_dashboard_screen.dart` | Set `childAspectRatio: 1.2`; added IST time indicators; synchronized config provider. |
| `smart_hostel_app/lib/features/staff/admin_settings_screen.dart` | Loaded config on init; validated `HH:MM` time format; refreshed staff dashboard on update. |
| `smart_hostel_app/lib/features/student/student_dashboard_screen.dart` | Added config fetch on init/refresh; removed hardcoded text; added IST server time, open/closed badges, and soft-guard dialog. |
| `smart_hostel_app/lib/features/attendance/location_verification_screen.dart` | Ensured configuration is fetched before GPS geofence checks. |
| `smart_hostel_app/lib/features/staff/student_detail_screen.dart` | Wrapped dialogs in `SingleChildScrollView`; replaced fixed chip rows with `Wrap`; made detail rows responsive. |

---

## 6. Deployment & Mobile Testing Guidance

1. **Deploy Backend to Render**:
   - Push backend changes to your deployment repository branch connected to Render.
   - Render will build and deploy the updated container.
   - All attendance window checks will now evaluate in Indian Standard Time (`UTC+05:30`), regardless of the container host timezone.

2. **Verify Configuration in Staff Console**:
   - Log in as staff (`staff@kpriet.ac.in`).
   - Navigate to Settings -> Geofence & Attendance Window.
   - The form will load current database values (`attendance_start_time` and `attendance_end_time`).
   - Update times in 24-hr `HH:MM` format (e.g. `18:00` to `22:00`).
   - Save settings; the staff dashboard will immediately reflect the new window and show `WINDOW OPEN` if current IST falls inside.

3. **Verify Student Attendance Registration**:
   - Log in as student.
   - Pull down to refresh the Student Dashboard.
   - The card will reflect the exact window in IST and the current server time in IST.
   - If the window is closed, tapping the button displays the exact allowed window and current time in IST.
   - If the window is open, the button activates and allows smooth progression through GPS and facial verification.
