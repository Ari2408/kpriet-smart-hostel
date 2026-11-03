import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../models/system_config_model.dart';
import '../services/api_service.dart';

class ConfigProvider extends ChangeNotifier {
  SystemConfigModel? _config;
  bool _isLoading = false;
  String? _errorMessage;

  SystemConfigModel? get config => _config;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchConfig() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await ApiService.get(ApiConstants.configUrl, requiresAuth: false);
      _config = SystemConfigModel.fromJson(response);
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<bool> updateConfig({
    required String campusName,
    required double campusLatitude,
    required double campusLongitude,
    required double geofenceRadiusMeters,
    required String attendanceStartTime,
    required String attendanceEndTime,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final payload = {
        "campus_name": campusName.trim(),
        "campus_latitude": campusLatitude,
        "campus_longitude": campusLongitude,
        "geofence_radius_meters": geofenceRadiusMeters,
        "attendance_start_time": attendanceStartTime.trim(),
        "attendance_end_time": attendanceEndTime.trim(),
      };

      final response = await ApiService.put(ApiConstants.configUrl, payload);
      _config = SystemConfigModel.fromJson(response);
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }
}
