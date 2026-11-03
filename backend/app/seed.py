import os
import datetime
import json
import base64
import numpy as np
import cv2
from sqlalchemy.orm import Session
from .database import engine, Base, SessionLocal
from .models import SystemConfig, Staff, Student, Attendance
from .security import hash_password
from .services.face_service import extract_face_embedding

def create_synthetic_portrait(name: str, hue: int = 15) -> str:
    """
    Creates a clear, synthetic face portrait image and returns base64.
    Used for seed profiles so every seeded student has a real 128D embedding.
    """
    img = np.full((240, 240, 3), 245, dtype=np.uint8) # light background
    # Hair / head outline
    cv2.circle(img, (120, 120), 82, (30, 30, 40), -1)
    # Face skin
    cv2.circle(img, (120, 125), 68, (160, 190, 225), -1)
    # Eyes
    cv2.circle(img, (95, 110), 8, (30, 30, 30), -1)
    cv2.circle(img, (145, 110), 8, (30, 30, 30), -1)
    # Nose
    cv2.line(img, (120, 118), (120, 142), (110, 140, 180), 3)
    # Smile
    cv2.ellipse(img, (120, 156), (24, 10), 0, 0, 180, (50, 60, 160), 3)

    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. System Config (Ensures basic campus geofence configuration exists)
        config = db.query(SystemConfig).first()
        if not config:
            config = SystemConfig(
                campus_name="KPR Institute of Engineering and Technology",
                campus_latitude=11.077711,
                campus_longitude=77.142223,
                geofence_radius_meters=800.0,
                attendance_start_time="19:00",
                attendance_end_time="20:00",
                liveness_strictness=0.65
            )
            db.add(config)
            db.commit()
            print("[Seed] System configuration created.")

        # Check if synthetic demo data creation is enabled
        should_seed_demo = os.getenv("SEED_DEMO_DATA", "false").lower() in ("true", "1", "yes")
        if not should_seed_demo:
            print("[Seed] SEED_DEMO_DATA is disabled or not set. Skipping demo data insertion.")
            return

        # 2. Staff Accounts
        if db.query(Staff).count() == 0:
            staff1 = Staff(
                staff_id="STF101",
                name="Dr. S. Sundararajan",
                email="warden@kpriet.ac.in",
                password_hash=hash_password("Warden@123"),
                role="warden",
                is_active=True
            )
            staff2 = Staff(
                staff_id="STF102",
                name="Prof. M. Kavitha",
                email="staff@kpriet.ac.in",
                password_hash=hash_password("Staff@123"),
                role="staff",
                is_active=True
            )
            db.add_all([staff1, staff2])
            db.commit()
            print("[Seed] Staff accounts seeded.")

        # 3. Student Accounts
        if db.query(Student).count() == 0:
            student_seeds = [
                {
                    "student_id": "KPR22CS001",
                    "register_number": "711321104001",
                    "name": "Aravind Kumar S",
                    "email": "711321104001@kpriet.ac.in",
                    "department": "Computer Science & Engineering",
                    "academic_year": 3,
                    "hostel_block": "Emerald Block",
                    "room_number": "B-201",
                    "phone_number": "+91 98765 43210"
                },
                {
                    "student_id": "KPR22AI002",
                    "register_number": "711321104002",
                    "name": "Deepika R",
                    "email": "711321104002@kpriet.ac.in",
                    "department": "Artificial Intelligence & Data Science",
                    "academic_year": 3,
                    "hostel_block": "Ruby Block",
                    "room_number": "A-105",
                    "phone_number": "+91 98765 43211"
                },
                {
                    "student_id": "KPR23EC003",
                    "register_number": "711321104003",
                    "name": "Karthik Raja M",
                    "email": "711321104003@kpriet.ac.in",
                    "department": "Electronics & Communication Engineering",
                    "academic_year": 2,
                    "hostel_block": "Diamond Block",
                    "room_number": "C-302",
                    "phone_number": "+91 98765 43212"
                },
                {
                    "student_id": "KPR21CS004",
                    "register_number": "711321104004",
                    "name": "Priyanka V",
                    "email": "711321104004@kpriet.ac.in",
                    "department": "Computer Science & Engineering",
                    "academic_year": 4,
                    "hostel_block": "Ruby Block",
                    "room_number": "A-210",
                    "phone_number": "+91 98765 43213"
                },
                {
                    "student_id": "KPR23ME005",
                    "register_number": "711321104005",
                    "name": "Sanjay Mohan",
                    "email": "711321104005@kpriet.ac.in",
                    "department": "Mechanical Engineering",
                    "academic_year": 2,
                    "hostel_block": "Emerald Block",
                    "room_number": "B-112",
                    "phone_number": "+91 98765 43214"
                },
                {
                    "student_id": "KPR24EC006",
                    "register_number": "711321104006",
                    "name": "Sneha B",
                    "email": "711321104006@kpriet.ac.in",
                    "department": "Electronics & Communication Engineering",
                    "academic_year": 1,
                    "hostel_block": "Pearl Block",
                    "room_number": "D-101",
                    "phone_number": "+91 98765 43215"
                }
            ]

            created_students = []
            for s_data in student_seeds:
                # Generate real facial embedding
                b64_img = create_synthetic_portrait(s_data["name"])
                nparr = np.frombuffer(base64.b64decode(b64_img), np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                emb = extract_face_embedding(img)

                student = Student(
                    student_id=s_data["student_id"],
                    register_number=s_data["register_number"],
                    name=s_data["name"],
                    email=s_data["email"],
                    password_hash=hash_password("Student@123"),
                    department=s_data["department"],
                    academic_year=s_data["academic_year"],
                    hostel_block=s_data["hostel_block"],
                    room_number=s_data["room_number"],
                    phone_number=s_data["phone_number"],
                    profile_photo_url=None,
                    facial_embedding=json.dumps(emb),
                    is_active=True
                )
                db.add(student)
                created_students.append(student)

            db.commit()
            print("[Seed] Student accounts seeded.")

            # 4. Historical Attendance Data for the past 14 days
            today = datetime.date.today()
            for s in created_students:
                for day_offset in range(1, 15):
                    hist_date = today - datetime.timedelta(days=day_offset)
                    # Sunday exclusion (assuming non-working day)
                    if hist_date.weekday() == 6:
                        continue

                    # Simulate 90% present, 10% absent
                    is_present = (day_offset + s.id) % 7 != 0
                    if is_present:
                        att = Attendance(
                            student_id=s.id,
                            attendance_date=hist_date,
                            attendance_time=datetime.time(19, 15 + (s.id * 3) % 35),
                            timestamp=datetime.datetime.combine(hist_date, datetime.time(19, 20)),
                            latitude=11.05450 + (s.id * 0.00005),
                            longitude=77.08645 + (s.id * 0.00005),
                            distance_from_campus=45.0 + (s.id * 10),
                            face_confidence=0.92,
                            liveness_passed=True,
                            status="PRESENT",
                            remarks="Verified via Facial Recognition"
                        )
                    else:
                        att = Attendance(
                            student_id=s.id,
                            attendance_date=hist_date,
                            attendance_time=datetime.time(20, 5),
                            timestamp=datetime.datetime.combine(hist_date, datetime.time(20, 5)),
                            latitude=0.0,
                            longitude=0.0,
                            distance_from_campus=0.0,
                            face_confidence=0.0,
                            liveness_passed=False,
                            status="ABSENT",
                            remarks="Attendance window closed - not marked"
                        )
                    db.add(att)

            db.commit()
            print("[Seed] Historical attendance seeded.")

    except Exception as e:
        db.rollback()
        print(f"[Seed Error] {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
