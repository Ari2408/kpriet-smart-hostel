import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import Attendance, Student
from ..security import require_staff
from ..services.report_service import generate_attendance_csv, generate_attendance_pdf
from ..services.attendance_service import get_current_system_config, get_ist_today

router = APIRouter(prefix="/api/reports", tags=["Reports & Analytics"])

def _fetch_records_for_report(
    db: Session,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    academic_year: Optional[int] = None
):
    from sqlalchemy import or_
    q = db.query(Attendance, Student).outerjoin(Student, Attendance.student_id == Student.id)

    if start_date:
        s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        q = q.filter(Attendance.attendance_date >= s_date)
    if end_date:
        e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        q = q.filter(Attendance.attendance_date <= e_date)
    if department and department != "All":
        q = q.filter(or_(Student.department == department, Attendance.anonymized_department == department))
    if academic_year:
        q = q.filter(or_(Student.academic_year == academic_year, Attendance.anonymized_academic_year == academic_year))

    results = q.order_by(desc(Attendance.attendance_date), desc(Attendance.attendance_time)).all()

    record_dicts = []
    for att, st in results:
        if st is not None:
            record_dicts.append({
                "id": att.id,
                "student_id": st.id,
                "student_name": st.name,
                "register_number": st.register_number,
                "department": st.department,
                "academic_year": st.academic_year,
                "hostel_room": f"{st.hostel_block} {st.room_number}",
                "attendance_date": att.attendance_date,
                "attendance_time": att.attendance_time.strftime("%I:%M %p"),
                "status": att.status,
                "distance_meters": att.distance_from_campus,
                "face_confidence": att.face_confidence,
                "remarks": att.remarks
            })
        else:
            # Preserved in privacy-preserving anonymized form without personal data
            record_dicts.append({
                "id": att.id,
                "student_id": 0,
                "student_name": "[Anonymized Student]",
                "register_number": "ARCHIVED",
                "department": att.anonymized_department or "General",
                "academic_year": att.anonymized_academic_year or 0,
                "hostel_room": "Archived",
                "attendance_date": att.attendance_date,
                "attendance_time": att.attendance_time.strftime("%I:%M %p"),
                "status": att.status,
                "distance_meters": att.distance_from_campus,
                "face_confidence": att.face_confidence,
                "remarks": "Anonymized record preserved for institutional compliance"
            })
    return record_dicts

@router.get("/summary")
def get_reports_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Returns high-level attendance aggregate reports broken down by department and year.
    """
    records = _fetch_records_for_report(db, start_date, end_date, department)
    total_records = len(records)
    total_present = sum(1 for r in records if r["status"] == "PRESENT")
    total_absent = sum(1 for r in records if r["status"] == "ABSENT")
    rate = round((total_present / max(1, total_records)) * 100.0, 1)

    # Department breakdown
    dept_stats = {}
    for r in records:
        d = r["department"]
        if d not in dept_stats:
            dept_stats[d] = {"present": 0, "absent": 0, "total": 0}
        dept_stats[d]["total"] += 1
        if r["status"] == "PRESENT":
            dept_stats[d]["present"] += 1
        else:
            dept_stats[d]["absent"] += 1

    return {
        "total_records": total_records,
        "total_present": total_present,
        "total_absent": total_absent,
        "attendance_rate_percentage": rate,
        "department_breakdown": dept_stats
    }

@router.get("/export/csv")
def export_csv_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Export attendance data to CSV format.
    """
    records = _fetch_records_for_report(db, start_date, end_date, department)
    csv_content = generate_attendance_csv(records)
    filename = f"KPRIET_Hostel_Attendance_{get_ist_today().strftime('%Y%m%d')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/pdf")
def export_pdf_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _staff: dict = Depends(require_staff)
):
    """
    Export official institutional attendance report to PDF.
    """
    records = _fetch_records_for_report(db, start_date, end_date, department)
    config = get_current_system_config(db)
    filter_label = department if (department and department != "All") else "All Departments"
    if start_date and end_date:
        filter_label += f" ({start_date} to {end_date})"

    pdf_bytes = generate_attendance_pdf(
        records=records,
        institution_name=config.campus_name,
        report_title="Daily & Monthly Attendance Summary",
        filter_info=filter_label
    )
    filename = f"KPRIET_Hostel_Report_{get_ist_today().strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
