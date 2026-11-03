import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../models/attendance_model.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';
import '../services/notification_service.dart';

class AttendanceProvider extends ChangeNotifier {
  LocationVerifyResult? _locationResult;
  bool _isVerifyingLocation = false;
  bool _isSubmitting = false;
  AttendanceSubmissionResponse? _lastSubmission;
  String? _errorMessage;

  LocationVerifyResult? get locationResult => _locationResult;
  bool get isVerifyingLocation => _isVerifyingLocation;
  bool get isSubmitting => _isSubmitting;
  AttendanceSubmissionResponse? get lastSubmission => _lastSubmission;
  String? get errorMessage => _errorMessage;

  void reset() {
    _locationResult = null;
    _isVerifyingLocation = false;
    _isSubmitting = false;
    _lastSubmission = null;
    _errorMessage = null;
    notifyListeners();
  }

  Future<bool> verifyLocation({
    double? campusLat,
    double? campusLon,
  }) async {
    _isVerifyingLocation = true;
    _errorMessage = null;
    notifyListeners();

    final locResult = await LocationService.getCurrentLocation(
      targetCampusLat: campusLat ?? ApiConstants.defaultCampusLat,
      targetCampusLon: campusLon ?? ApiConstants.defaultCampusLon,
    );

    if (!locResult.success) {
      _isVerifyingLocation = false;
      _errorMessage = locResult.errorMessage;
      notifyListeners();
      return false;
    }

    try {
      final response = await ApiService.post(
        ApiConstants.verifyLocationUrl,
        {
          "latitude": locResult.latitude,
          "longitude": locResult.longitude,
          "is_mock": locResult.isMocked,
        },
      );

      _locationResult = LocationVerifyResult.fromJson(
        response,
        lat: locResult.latitude,
        lon: locResult.longitude,
      );
      _isVerifyingLocation = false;
      notifyListeners();
      return _locationResult?.insideGeofence ?? false;
    } catch (e) {
      _isVerifyingLocation = false;
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> submitAttendance({
    required double latitude,
    required double longitude,
    required bool isMock,
    required String faceImageBase64,
    String? livenessChallengeResponse,
    String? testTimeOverride,
  }) async {
    _isSubmitting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final payload = {
        "latitude": latitude,
        "longitude": longitude,
        "is_mock": isMock,
        "face_image_base64": faceImageBase64,
        "liveness_challenge_response": livenessChallengeResponse ?? "passed",
        if (testTimeOverride != null) "test_time_override": testTimeOverride,
      };

      final response = await ApiService.post(
        ApiConstants.submitAttendanceUrl,
        payload,
      );

      _lastSubmission = AttendanceSubmissionResponse.fromJson(response);
      _isSubmitting = false;
      notifyListeners();

      // Trigger success notification
      NotificationService.notifyAttendanceSuccess(_lastSubmission!.attendanceTime);

      return true;
    } catch (e) {
      _isSubmitting = false;
      _errorMessage = e.toString();
      notifyListeners();

      NotificationService.notifyVerificationFailure(e.toString());
      return false;
    }
  }

  Future<StartVerificationSession?> startVerificationSession() async {
    try {
      final response = await ApiService.post(
        ApiConstants.startVerificationUrl,
        {},
      );
      return StartVerificationSession.fromJson(response);
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<VerifyFaceResult?> verifyFace({
    required String sessionToken,
    required String faceImageBase64,
    required String challengeActionDetected,
  }) async {
    try {
      final response = await ApiService.post(
        ApiConstants.verifyFaceUrl,
        {
          "session_token": sessionToken,
          "face_image_base64": faceImageBase64,
          "challenge_action_detected": challengeActionDetected,
        },
      );
      return VerifyFaceResult.fromJson(response);
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<bool> markAttendanceWithSession({
    required String sessionToken,
    required double latitude,
    required double longitude,
    bool isMock = false,
    String? testTimeOverride,
  }) async {
    _isSubmitting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final payload = {
        "session_token": sessionToken,
        "latitude": latitude,
        "longitude": longitude,
        "is_mock": isMock,
        if (testTimeOverride != null) "test_time_override": testTimeOverride,
      };

      final response = await ApiService.post(
        ApiConstants.markAttendanceUrl,
        payload,
      );

      _lastSubmission = AttendanceSubmissionResponse.fromJson(response);
      _isSubmitting = false;
      notifyListeners();

      NotificationService.notifyAttendanceSuccess(_lastSubmission!.attendanceTime);
      return true;
    } catch (e) {
      _isSubmitting = false;
      _errorMessage = e.toString();
      notifyListeners();

      NotificationService.notifyVerificationFailure(e.toString());
      return false;
    }
  }
}

