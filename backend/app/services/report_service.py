import csv
import io
import datetime
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_attendance_csv(records: List[Dict[str, Any]]) -> str:
    """
    Generates CSV formatted string from attendance records list.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Record ID",
        "Student Name",
        "Register Number",
        "Department",
        "Year",
        "Hostel Room",
        "Date",
        "Time",
        "Status",
        "Distance (m)",
        "Face Confidence (%)",
        "Remarks"
    ])

    for r in records:
        writer.writerow([
            r.get("id", ""),
            r.get("student_name", ""),
            r.get("register_number", ""),
            r.get("department", ""),
            r.get("academic_year", ""),
            r.get("hostel_room", ""),
            str(r.get("attendance_date", "")),
            r.get("attendance_time", ""),
            r.get("status", ""),
            r.get("distance_meters", ""),
            f"{r.get('face_confidence', 0.0) * 100:.1f}",
            r.get("remarks", "")
        ])

    return output.getvalue()

def generate_attendance_pdf(
    records: List[Dict[str, Any]],
    institution_name: str = "KPR Institute of Engineering and Technology",
    report_title: str = "Hostel Attendance Report",
    filter_info: str = "All Records"
) -> bytes:
    """
    Generates a PDF report using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0D47A1"),
        alignment=1 # Center
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#37474F"),
        alignment=1
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#546E7A"),
        alignment=1
    )

    elements.append(Paragraph(institution_name.upper(), title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"Smart Hostel Management System &bull; {report_title}", subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        f"Generated on {datetime.datetime.now().strftime('%d %B %Y, %I:%M %p')} | Scope: {filter_info}",
        meta_style
    ))
    elements.append(Spacer(1, 14))

    # Metric summaries
    total = len(records)
    present_cnt = sum(1 for r in records if r.get("status") == "PRESENT")
    absent_cnt = sum(1 for r in records if r.get("status") == "ABSENT")
    rate = (present_cnt / max(1, total)) * 100.0

    summary_data = [
        ["Total Records", "Present", "Absent", "Attendance Rate"],
        [str(total), str(present_cnt), str(absent_cnt), f"{rate:.1f}%"]
    ]
    summary_table = Table(summary_data, colWidths=[130, 130, 130, 130])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ECEFF1")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#263238")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CFD8DC")),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # Records Table
    table_header = ["Reg No", "Student Name", "Dept", "Room", "Date", "Time", "Status", "Confidence"]
    table_rows = [table_header]

    for r in records[:150]: # Cap at 150 rows for performance
        conf = f"{r.get('face_confidence', 0.0) * 100:.0f}%" if r.get('status') == 'PRESENT' else "-"
        table_rows.append([
            r.get("register_number", "")[-8:], # short reg no
            r.get("student_name", "")[:18],
            r.get("department", "")[:10],
            r.get("hostel_room", "")[:8],
            str(r.get("attendance_date", ""))[-5:], # MM-DD
            r.get("attendance_time", ""),
            r.get("status", ""),
            conf
        ])

    data_table = Table(table_rows, colWidths=[65, 110, 65, 55, 55, 65, 60, 60])
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0D47A1")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CFD8DC")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(data_table)

    doc.build(elements)
    return buffer.getvalue()
