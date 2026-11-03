import 'attendance_model.dart';

class StudentDashboardData {
  final int studentId;
  final String name;
  final String registerNumber;
  final String department;
  final String hostelRoom;
  final String? profilePhotoUrl;
  final String todayStatus; // "PRESENT", "ABSENT", "PENDING"
  final String? todayAttendanceTime;
  final bool isWindowOpen;
  final String windowStart;
  final String windowEnd;
  final String currentServerTime;
  final int totalPresentDays;
  final int totalAbsentDays;
  final int totalApplicableDays;
  final double attendancePercentage;
  final List<AttendanceRecordItem> recentHistory;
  final Map<String, dynamic> monthlySummary;

  StudentDashboardData({
    required this.studentId,
    required this.name,
    required this.registerNumber,
    required this.department,
    required this.hostelRoom,
    this.profilePhotoUrl,
    required this.todayStatus,
    this.todayAttendanceTime,
    required this.isWindowOpen,
    required this.windowStart,
    required this.windowEnd,
    required this.currentServerTime,
    required this.totalPresentDays,
    required this.totalAbsentDays,
    required this.totalApplicableDays,
    required this.attendancePercentage,
    required this.recentHistory,
    required this.monthlySummary,
  });

  factory StudentDashboardData.fromJson(Map<String, dynamic> json) {
    var rawList = json['recent_history'] as List? ?? [];
    List<AttendanceRecordItem> history = rawList
        .map((item) => AttendanceRecordItem.fromJson(item))
        .toList();

    return StudentDashboardData(
      studentId: json['student_id'] ?? 0,
      name: json['name'] ?? '',
      registerNumber: json['register_number'] ?? '',
      department: json['department'] ?? '',
      hostelRoom: json['hostel_room'] ?? '',
      profilePhotoUrl: json['profile_photo_url'],
      todayStatus: json['today_status'] ?? 'PENDING',
      todayAttendanceTime: json['today_attendance_time'],
      isWindowOpen: json['is_window_open'] ?? false,
      windowStart: json['window_start'] ?? '19:00',
      windowEnd: json['window_end'] ?? '20:00',
      currentServerTime: json['current_server_time'] ?? '',
      totalPresentDays: json['total_present_days'] ?? 0,
      totalAbsentDays: json['total_absent_days'] ?? 0,
      totalApplicableDays: json['total_applicable_days'] ?? 0,
      attendancePercentage: (json['attendance_percentage'] as num?)?.toDouble() ?? 100.0,
      recentHistory: history,
      monthlySummary: json['monthly_summary'] as Map<String, dynamic>? ?? {},
    );
  }
}

class StaffDashboardData {
  final int totalStudents;
  final int presentToday;
  final int absentToday;
  final int pendingToday;
  final bool attendanceWindowOpen;
  final String windowStart;
  final String windowEnd;
  final String serverTime;
  final List<AttendanceRecordItem> records;

  StaffDashboardData({
    required this.totalStudents,
    required this.presentToday,
    required this.absentToday,
    required this.pendingToday,
    required this.attendanceWindowOpen,
    required this.windowStart,
    required this.windowEnd,
    required this.serverTime,
    required this.records,
  });

  factory StaffDashboardData.fromJson(Map<String, dynamic> json) {
    var rawList = json['records'] as List? ?? [];
    List<AttendanceRecordItem> recordList = rawList
        .map((item) => AttendanceRecordItem.fromJson(item))
        .toList();

    return StaffDashboardData(
      totalStudents: json['total_students'] ?? 0,
      presentToday: json['present_today'] ?? 0,
      absentToday: json['absent_today'] ?? 0,
      pendingToday: json['pending_today'] ?? 0,
      attendanceWindowOpen: json['attendance_window_open'] ?? false,
      windowStart: json['window_start'] ?? '19:00',
      windowEnd: json['window_end'] ?? '20:00',
      serverTime: json['server_time'] ?? '',
      records: recordList,
    );
  }
}
