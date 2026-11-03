class AttendanceRecordItem {
  final int id;
  final int studentId;
  final String studentName;
  final String registerNumber;
  final String department;
  final String hostelRoom;
  final String attendanceDate;
  final String attendanceTime;
  final double latitude;
  final double longitude;
  final double distanceMeters;
  final double faceConfidence;
  final String status; // "PRESENT", "ABSENT", "PENDING"
  final String? remarks;

  AttendanceRecordItem({
    required this.id,
    required this.studentId,
    required this.studentName,
    required this.registerNumber,
    required this.department,
    required this.hostelRoom,
    required this.attendanceDate,
    required this.attendanceTime,
    required this.latitude,
    required this.longitude,
    required this.distanceMeters,
    required this.faceConfidence,
    required this.status,
    this.remarks,
  });

  bool get isPresent => status.toUpperCase() == "PRESENT";
  bool get isAbsent => status.toUpperCase() == "ABSENT";
  bool get isPending => status.toUpperCase() == "PENDING";

  factory AttendanceRecordItem.fromJson(Map<String, dynamic> json) {
    return AttendanceRecordItem(
      id: json['id'] ?? 0,
      studentId: json['student_id'] ?? 0,
      studentName: json['student_name'] ?? '',
      registerNumber: json['register_number'] ?? '',
      department: json['department'] ?? '',
      hostelRoom: json['hostel_room'] ?? '',
      attendanceDate: json['attendance_date']?.toString() ?? '',
      attendanceTime: json['attendance_time'] ?? '',
      latitude: (json['latitude'] as num?)?.toDouble() ?? 0.0,
      longitude: (json['longitude'] as num?)?.toDouble() ?? 0.0,
      distanceMeters: (json['distance_meters'] as num?)?.toDouble() ?? 0.0,
      faceConfidence: (json['face_confidence'] as num?)?.toDouble() ?? 0.0,
      status: json['status'] ?? 'PENDING',
      remarks: json['remarks'],
    );
  }
}

class LocationVerifyResult {
  final bool insideGeofence;
  final double distanceMeters;
  final double radiusMeters;
  final String campusName;
  final String message;
  final double latitude;
  final double longitude;

  LocationVerifyResult({
    required this.insideGeofence,
    required this.distanceMeters,
    required this.radiusMeters,
    required this.campusName,
    required this.message,
    this.latitude = 0.0,
    this.longitude = 0.0,
  });

  factory LocationVerifyResult.fromJson(Map<String, dynamic> json, {double lat = 0.0, double lon = 0.0}) {
    return LocationVerifyResult(
      insideGeofence: json['inside_geofence'] ?? false,
      distanceMeters: (json['distance_meters'] as num?)?.toDouble() ?? -1.0,
      radiusMeters: (json['radius_meters'] as num?)?.toDouble() ?? 600.0,
      campusName: json['campus_name'] ?? 'KPRIET Campus',
      message: json['message'] ?? '',
      latitude: (json['latitude'] as num?)?.toDouble() ?? lat,
      longitude: (json['longitude'] as num?)?.toDouble() ?? lon,
    );
  }
}

class AttendanceSubmissionResponse {
  final int id;
  final int studentId;
  final String studentName;
  final String registerNumber;
  final String attendanceDate;
  final String attendanceTime;
  final String status;
  final double distanceFromCampus;
  final double faceConfidence;
  final String message;

  AttendanceSubmissionResponse({
    required this.id,
    required this.studentId,
    required this.studentName,
    required this.registerNumber,
    required this.attendanceDate,
    required this.attendanceTime,
    required this.status,
    required this.distanceFromCampus,
    required this.faceConfidence,
    required this.message,
  });

  factory AttendanceSubmissionResponse.fromJson(Map<String, dynamic> json) {
    return AttendanceSubmissionResponse(
      id: json['id'] ?? 0,
      studentId: json['student_id'] ?? 0,
      studentName: json['student_name'] ?? '',
      registerNumber: json['register_number'] ?? '',
      attendanceDate: json['attendance_date']?.toString() ?? '',
      attendanceTime: json['attendance_time'] ?? '',
      status: json['status'] ?? 'PRESENT',
      distanceFromCampus: (json['distance_from_campus'] as num?)?.toDouble() ?? 0.0,
      faceConfidence: (json['face_confidence'] as num?)?.toDouble() ?? 0.0,
      message: json['message'] ?? 'Attendance Registered',
    );
  }
}

class AbsentStudentItem {
  final int studentId;
  final String name;
  final String registerNumber;
  final String department;
  final int academicYear;
  final String hostelBlock;
  final String roomNumber;
  final String? phoneNumber;
  final String? profilePhotoUrl;
  final String status;

  AbsentStudentItem({
    required this.studentId,
    required this.name,
    required this.registerNumber,
    required this.department,
    required this.academicYear,
    required this.hostelBlock,
    required this.roomNumber,
    this.phoneNumber,
    this.profilePhotoUrl,
    required this.status,
  });

  factory AbsentStudentItem.fromJson(Map<String, dynamic> json) {
    return AbsentStudentItem(
      studentId: json['student_id'] ?? 0,
      name: json['name'] ?? '',
      registerNumber: json['register_number'] ?? '',
      department: json['department'] ?? '',
      academicYear: json['academic_year'] ?? 1,
      hostelBlock: json['hostel_block'] ?? '',
      roomNumber: json['room_number'] ?? '',
      phoneNumber: json['phone_number'],
      profilePhotoUrl: json['profile_photo_url'],
      status: json['status'] ?? 'ABSENT',
    );
  }
}

class StartVerificationSession {
  final String sessionToken;
  final String challengeType;
  final String challengePrompt;
  final int expiresInSeconds;

  StartVerificationSession({
    required this.sessionToken,
    required this.challengeType,
    required this.challengePrompt,
    required this.expiresInSeconds,
  });

  factory StartVerificationSession.fromJson(Map<String, dynamic> json) {
    return StartVerificationSession(
      sessionToken: json['session_token'] ?? '',
      challengeType: json['challenge_type'] ?? '',
      challengePrompt: json['challenge_prompt'] ?? '',
      expiresInSeconds: json['expires_in_seconds'] ?? 90,
    );
  }
}

class VerifyFaceResult {
  final bool verified;
  final bool livenessPassed;
  final double similarityScore;
  final String message;

  VerifyFaceResult({
    required this.verified,
    required this.livenessPassed,
    required this.similarityScore,
    required this.message,
  });

  factory VerifyFaceResult.fromJson(Map<String, dynamic> json) {
    return VerifyFaceResult(
      verified: json['verified'] ?? false,
      livenessPassed: json['liveness_passed'] ?? false,
      similarityScore: (json['similarity_score'] as num?)?.toDouble() ?? 0.0,
      message: json['message'] ?? '',
    );
  }
}

