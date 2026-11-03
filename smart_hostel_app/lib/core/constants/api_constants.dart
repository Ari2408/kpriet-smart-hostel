class ApiConstants {
  // Default to Android Emulator localhost; configurable in settings or via AppConfig
  static String baseUrl = "http://10.0.2.2:8000";

  // Auth endpoints
  static String get loginUrl => "$baseUrl/api/auth/login";
  static String get meUrl => "$baseUrl/api/auth/me";
  static String get changePasswordUrl => "$baseUrl/api/auth/change-password";

  // Student endpoints
  static String get studentsUrl => "$baseUrl/api/students";
  static String studentDetailUrl(int id) => "$baseUrl/api/students/$id";
  static String resetStudentPasswordUrl(int id) => "$baseUrl/api/students/$id/reset-password";
  static String deleteStudentUrl(int id, String confirmRegNo) =>
      "$baseUrl/api/students/$id?confirm_register_number=${Uri.encodeComponent(confirmRegNo)}";

  // Attendance endpoints
  static String get verifyLocationUrl => "$baseUrl/api/attendance/verify-location";
  static String get submitAttendanceUrl => "$baseUrl/api/attendance/submit";
  static String get startVerificationUrl => "$baseUrl/api/attendance/start-verification";
  static String get verifyFaceUrl => "$baseUrl/api/attendance/verify-face";
  static String get markAttendanceUrl => "$baseUrl/api/attendance/mark";
  static String get studentDashboardUrl => "$baseUrl/api/attendance/dashboard/student";
  static String get staffDashboardUrl => "$baseUrl/api/attendance/dashboard/staff";
  static String get absenteesUrl => "$baseUrl/api/attendance/absentees";
  static String get historyUrl => "$baseUrl/api/attendance/history";

  // Reports
  static String get reportsSummaryUrl => "$baseUrl/api/reports/summary";
  static String get exportCsvUrl => "$baseUrl/api/reports/export/csv";
  static String get exportPdfUrl => "$baseUrl/api/reports/export/pdf";

  // Config
  static String get configUrl => "$baseUrl/api/config";

  // Default KPRIET Campus Geofence Constants
  static const String defaultCampusName = "KPR Institute of Engineering and Technology";
  static const double defaultCampusLat = 11.05445;
  static const double defaultCampusLon = 77.08641;
  static const double defaultRadiusMeters = 600.0;
  static const String defaultStartTime = "19:00"; // 7:00 PM
  static const String defaultEndTime = "20:00";   // 8:00 PM
}
