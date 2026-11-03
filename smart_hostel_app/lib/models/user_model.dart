class UserModel {
  final int id;
  final String role; // "student", "staff", "warden", "admin"
  final String name;
  final String identifier; // register_number or staff_id
  final String? email;
  final String? department;
  final int? academicYear;
  final String? hostelBlock;
  final String? roomNumber;
  final String? phoneNumber;
  final String? profilePhotoUrl;
  final bool isActive;

  UserModel({
    required this.id,
    required this.role,
    required this.name,
    required this.identifier,
    this.email,
    this.department,
    this.academicYear,
    this.hostelBlock,
    this.roomNumber,
    this.phoneNumber,
    this.profilePhotoUrl,
    this.isActive = true,
  });

  bool get isStudent => role == "student";
  bool get isStaff => role == "staff" || role == "warden" || role == "admin";

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] ?? json['user_id'] ?? 0,
      role: json['role'] ?? 'student',
      name: json['name'] ?? '',
      identifier: json['identifier'] ?? json['register_number'] ?? json['staff_id'] ?? '',
      email: json['email'],
      department: json['department'],
      academicYear: json['academic_year'],
      hostelBlock: json['hostel_block'],
      roomNumber: json['room_number'],
      phoneNumber: json['phone_number'],
      profilePhotoUrl: json['profile_photo_url'],
      isActive: json['is_active'] ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'role': role,
      'name': name,
      'identifier': identifier,
      'email': email,
      'department': department,
      'academic_year': academicYear,
      'hostel_block': hostelBlock,
      'room_number': roomNumber,
      'phone_number': phoneNumber,
      'profile_photo_url': profilePhotoUrl,
      'is_active': isActive,
    };
  }
}

class AuthTokenResponse {
  final String accessToken;
  final String tokenType;
  final String role;
  final int userId;
  final String name;
  final String identifier;
  final String? department;
  final String? profilePhotoUrl;

  AuthTokenResponse({
    required this.accessToken,
    required this.tokenType,
    required this.role,
    required this.userId,
    required this.name,
    required this.identifier,
    this.department,
    this.profilePhotoUrl,
  });

  factory AuthTokenResponse.fromJson(Map<String, dynamic> json) {
    return AuthTokenResponse(
      accessToken: json['access_token'] ?? '',
      tokenType: json['token_type'] ?? 'bearer',
      role: json['role'] ?? 'student',
      userId: json['user_id'] ?? 0,
      name: json['name'] ?? '',
      identifier: json['identifier'] ?? '',
      department: json['department'],
      profilePhotoUrl: json['profile_photo_url'],
    );
  }
}
