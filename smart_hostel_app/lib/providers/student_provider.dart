import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../models/dashboard_models.dart';
import '../services/api_service.dart';

class StudentProvider extends ChangeNotifier {
  StudentDashboardData? _dashboardData;
  bool _isLoading = false;
  String? _errorMessage;

  StudentDashboardData? get dashboardData => _dashboardData;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchDashboard() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await ApiService.get(ApiConstants.studentDashboardUrl);
      _dashboardData = StudentDashboardData.fromJson(response);
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString();
      notifyListeners();
    }
  }
}
