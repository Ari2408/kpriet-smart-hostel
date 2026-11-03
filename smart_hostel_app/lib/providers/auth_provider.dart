import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../models/user_model.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

class AuthProvider extends ChangeNotifier {
  UserModel? _currentUser;
  String? _token;
  bool _isLoading = false;
  String? _errorMessage;

  UserModel? get currentUser => _currentUser;
  String? get token => _token;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _token != null && _currentUser != null;
  bool get isStudent => _currentUser?.isStudent ?? false;
  bool get isStaff => _currentUser?.isStaff ?? false;

  Future<bool> checkAutoLogin() async {
    _isLoading = true;
    notifyListeners();

    try {
      final savedUrl = await StorageService.getBaseUrl();
      if (savedUrl != null && savedUrl.isNotEmpty) {
        // Automatically upgrade legacy local emulator URLs to the production cloud URL
        if (savedUrl == "http://10.0.2.2:8000" || savedUrl == "http://127.0.0.1:8000") {
          ApiConstants.baseUrl = ApiConstants.productionBaseUrl;
          await StorageService.saveBaseUrl(ApiConstants.productionBaseUrl);
        } else {
          ApiConstants.baseUrl = savedUrl;
        }
      } else {
        // Default to production cloud URL and persist
        ApiConstants.baseUrl = ApiConstants.productionBaseUrl;
      }

      final savedToken = await StorageService.getToken();
      final savedUser = await StorageService.getUser();

      if (savedToken != null && savedUser != null) {
        _token = savedToken;
        _currentUser = savedUser;
        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (_) {}

    _isLoading = false;
    notifyListeners();
    return false;
  }

  Future<bool> login({
    required String username,
    required String password,
    String? roleHint,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await ApiService.post(
        ApiConstants.loginUrl,
        {
          "username": username.trim(),
          "password": password,
          "role_hint": roleHint,
        },
        requiresAuth: false,
      );

      final tokenResp = AuthTokenResponse.fromJson(response);
      _token = tokenResp.accessToken;

      _currentUser = UserModel(
        id: tokenResp.userId,
        role: tokenResp.role,
        name: tokenResp.name,
        identifier: tokenResp.identifier,
        department: tokenResp.department,
        profilePhotoUrl: tokenResp.profilePhotoUrl,
      );

      await StorageService.saveSession(
        token: _token!,
        role: tokenResp.role,
        user: _currentUser!,
      );

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

  Future<bool> changePassword(String currentPassword, String newPassword) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await ApiService.post(
        ApiConstants.changePasswordUrl,
        {
          "current_password": currentPassword,
          "new_password": newPassword,
        },
      );
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

  Future<void> logout() async {
    _currentUser = null;
    _token = null;
    _errorMessage = null;
    await StorageService.clearSession();
    notifyListeners();
  }

  void updateBackendUrl(String newUrl) {
    ApiConstants.baseUrl = newUrl;
    StorageService.saveBaseUrl(newUrl);
    notifyListeners();
  }
}
