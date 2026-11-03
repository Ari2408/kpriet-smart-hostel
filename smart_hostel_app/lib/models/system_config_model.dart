class SystemConfigModel {
  final int? id;
  final String campusName;
  final double campusLatitude;
  final double campusLongitude;
  final double geofenceRadiusMeters;
  final String attendanceStartTime;
  final String attendanceEndTime;
  final double livenessStrictness;
  final bool isWindowOpen;
  final String? currentTimeIst;
  final String? serverTimezone;

  SystemConfigModel({
    this.id,
    required this.campusName,
    required this.campusLatitude,
    required this.campusLongitude,
    required this.geofenceRadiusMeters,
    required this.attendanceStartTime,
    required this.attendanceEndTime,
    this.livenessStrictness = 0.65,
    this.isWindowOpen = false,
    this.currentTimeIst,
    this.serverTimezone,
  });

  factory SystemConfigModel.fromJson(Map<String, dynamic> json) {
    return SystemConfigModel(
      id: json['id'],
      campusName: json['campus_name'] ?? 'KPR Institute of Engineering and Technology',
      campusLatitude: (json['campus_latitude'] as num?)?.toDouble() ?? 11.05445,
      campusLongitude: (json['campus_longitude'] as num?)?.toDouble() ?? 77.08641,
      geofenceRadiusMeters: (json['geofence_radius_meters'] as num?)?.toDouble() ?? 600.0,
      attendanceStartTime: json['attendance_start_time'] ?? '19:00',
      attendanceEndTime: json['attendance_end_time'] ?? '20:00',
      livenessStrictness: (json['liveness_strictness'] as num?)?.toDouble() ?? 0.65,
      isWindowOpen: json['is_window_open'] as bool? ?? false,
      currentTimeIst: json['current_time_ist'] as String?,
      serverTimezone: json['server_timezone'] as String? ?? 'Asia/Kolkata (IST)',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'campus_name': campusName,
      'campus_latitude': campusLatitude,
      'campus_longitude': campusLongitude,
      'geofence_radius_meters': geofenceRadiusMeters,
      'attendance_start_time': attendanceStartTime,
      'attendance_end_time': attendanceEndTime,
      'liveness_strictness': livenessStrictness,
    };
  }
}
