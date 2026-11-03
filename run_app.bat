@echo off
title Smart Hostel Attendance - Flutter Mobile App
echo ==============================================================
echo Launching KPRIET Smart Hostel Attendance Mobile Application...
echo ==============================================================
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot
set PATH=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot\bin;%PATH%
cd /d "%~dp0smart_hostel_app"
flutter run
pause
