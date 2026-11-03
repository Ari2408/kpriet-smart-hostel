@echo off
title Smart Hostel Attendance - FastAPI Server
echo ==============================================================
echo Starting KPRIET Smart Hostel Attendance Backend Server...
echo ==============================================================
cd /d "%~dp0backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
