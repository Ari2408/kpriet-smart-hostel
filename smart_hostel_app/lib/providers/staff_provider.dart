import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../models/dashboard_models.dart';
import '../models/attendance_model.dart';
import '../models/user_model.dart';
import '../services/api_service.dart';

class StaffProvider extends ChangeNotifier {
  StaffDashboardData? _dashboardData;
  List<AbsentStudentItem> _absentees = [];
  List<UserModel> _students = [];

  bool _isLoading = false;
  String? _errorMessage;

  String _statusFilter = "ALL";
  String _departmentFilter = "All";
  String _searchQuery = "";

  StaffDashboardData? get dashboardData => _dashboardData;
  List<AbsentStudentItem> get absentees => _absentees;
  List<UserModel> get students => _students;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String get statusFilter => _statusFilter;
  String get departmentFilter => _departmentFilter;
  String get searchQuery => _searchQuery;

  void setStatusFilter(String filter) {
    _statusFilter = filter;
    fetchDashboard();
  }

  void setDepartmentFilter(String dept) {
    _departmentFilter = dept;
    fetchDashboard();
  }

  void setSearchQuery(String q) {
    _searchQuery = q;
    fetchDashboard();
  }

  Future<void> fetchDashboard() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final queryParams = <String, String>{};
      if (_statusFilter != "ALL") queryParams["status_filter"] = _statusFilter;
      if (_departmentFilter != "All") queryParams["department"] = _departmentFilter;
      if (_searchQuery.isNotEmpty) queryParams["query"] = _searchQuery;

      final uri = Uri.parse(ApiConstants.staffDashboardUrl).replace(queryParameters: queryParams);
      final response = await ApiService.get(uri.toString());

      _dashboardData = StaffDashboardData.fromJson(response);
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> fetchAbsentees({String? department}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final queryParams = <String, String>{};
      if (department != null && department != "All") {
        queryParams["department"] = department;
      }
      final uri = Uri.parse(ApiConstants.absenteesUrl).replace(queryParameters: queryParams);
      final response = await ApiService.get(uri.toString());

      if (response is List) {
        _absentees = response.map((item) => AbsentStudentItem.fromJson(item)).toList();
      }
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> fetchStudents({String? query, String? department}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final queryParams = <String, String>{};
      if (query != null && query.isNotEmpty) queryParams["query"] = query;
      if (department != null && department != "All") queryParams["department"] = department;

      final uri = Uri.parse(ApiConstants.studentsUrl).replace(queryParameters: queryParams);
      final response = await ApiService.get(uri.toString());

      if (response is List) {
        _students = response.map((item) => UserModel.fromJson(item)).toList();
      }
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<bool> addStudent({
    String? studentId,
    required String registerNumber,
    required String name,
    String? email,
    required String password,
    String? confirmPassword,
    required String department,
    required int academicYear,
    required String hostelBlock,
    required String roomNumber,
    String? phoneNumber,
    required String profileImageBase64,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final sId = studentId?.trim();
      final mail = email?.trim();
      final payload = {
        if (sId != null && sId.isNotEmpty) "student_id": sId,
        "register_number": registerNumber.trim(),
        "name": name.trim(),
        if (mail != null && mail.isNotEmpty) "email": mail,
        "password": password,
        "confirm_password": confirmPassword ?? password,
        "department": department,
        "academic_year": academicYear,
        "hostel_block": hostelBlock.trim(),
        "room_number": roomNumber.trim(),
        "phone_number": phoneNumber?.trim(),
        "profile_image_base64": profileImageBase64,
      };

      await ApiService.post(ApiConstants.studentsUrl, payload);
      await fetchStudents();
      await fetchDashboard();
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

  Future<bool> deleteStudentPermanently(int studentId, String confirmRegisterNumber) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      final url = ApiConstants.deleteStudentUrl(studentId, confirmRegisterNumber);
      await ApiService.delete(url);
      await fetchStudents();
      await fetchDashboard();
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

  Future<bool> resetStudentPassword(int studentId, String newPassword) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      final url = ApiConstants.resetStudentPasswordUrl(studentId);
      await ApiService.post(url, {"new_password": newPassword});
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

