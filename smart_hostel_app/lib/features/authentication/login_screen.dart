import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/constants/api_constants.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    // Pre-fill demo student by default for smooth evaluation
    _usernameController.text = "711321104001";
    _passwordController.text = "Student@123";

    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        if (_tabController.index == 0) {
          _usernameController.text = "711321104001";
          _passwordController.text = "Student@123";
        } else {
          _usernameController.text = "staff@kpriet.ac.in";
          _passwordController.text = "Staff@123";
        }
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submitLogin() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;

    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please enter both credentials")),
      );
      return;
    }

    final roleHint = _tabController.index == 0 ? "student" : "staff";
    final auth = context.read<AuthProvider>();

    final success = await auth.login(
      username: username,
      password: password,
      roleHint: roleHint,
    );

    if (!mounted) return;

    if (success) {
      if (auth.isStudent) {
        Navigator.pushReplacementNamed(context, '/student-dashboard');
      } else {
        Navigator.pushReplacementNamed(context, '/staff-dashboard');
      }
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(auth.errorMessage ?? "Login failed"),
          backgroundColor: AppColors.absentRed,
        ),
      );
    }
  }

  void _showServerSettingsDialog() {
    final urlController = TextEditingController(text: ApiConstants.baseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Backend Server Settings"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Configure backend host for emulator, physical device or LAN:",
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: urlController,
              decoration: const InputDecoration(
                labelText: "Server Base URL",
                hintText: "http://10.0.2.2:8000 or http://192.168.1.X:8000",
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              children: [
                ActionChip(
                  label: const Text("Emulator (10.0.2.2)"),
                  onPressed: () => urlController.text = "http://10.0.2.2:8000",
                ),
                ActionChip(
                  label: const Text("Localhost (127.0.0.1)"),
                  onPressed: () => urlController.text = "http://127.0.0.1:8000",
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text("Cancel"),
          ),
          ElevatedButton(
            onPressed: () {
              context.read<AuthProvider>().updateBackendUrl(urlController.text.trim());
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text("Server URL updated to ${urlController.text.trim()}")),
              );
            },
            child: const Text("Save"),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_ethernet_rounded, color: AppColors.primaryNavy),
            tooltip: "Server Configuration",
            onPressed: _showServerSettingsDialog,
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Center(
                child: Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: AppColors.primaryNavy,
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: const Icon(Icons.apartment_rounded, color: Colors.white, size: 40),
                ),
              ),
              const SizedBox(height: 20),
              const Center(
                child: Text(
                  "KPR Institute of Engineering and Technology",
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textSecondary,
                    letterSpacing: 0.8,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 4),
              const Center(
                child: Text(
                  "Hostel Attendance Portal",
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: AppColors.primaryNavy,
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Role Tab Selector
              Container(
                decoration: BoxDecoration(
                  color: AppColors.surfaceMuted,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: TabBar(
                  controller: _tabController,
                  indicator: BoxDecoration(
                    color: AppColors.primaryNavy,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  labelColor: Colors.white,
                  unselectedLabelColor: AppColors.textSecondary,
                  indicatorSize: TabBarIndicatorSize.tab,
                  dividerColor: Colors.transparent,
                  tabs: const [
                    Tab(
                      icon: Icon(Icons.school_rounded, size: 20),
                      text: "Student Login",
                    ),
                    Tab(
                      icon: Icon(Icons.admin_panel_settings_rounded, size: 20),
                      text: "Staff / Admin",
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),

              // Form fields
              TextField(
                controller: _usernameController,
                decoration: InputDecoration(
                  labelText: _tabController.index == 0 ? "Register Number" : "Staff ID or Email",
                  hintText: _tabController.index == 0 ? "e.g. 711321104001" : "e.g. staff@kpriet.ac.in",
                  prefixIcon: const Icon(Icons.badge_outlined, color: AppColors.primaryNavy),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _passwordController,
                obscureText: _obscurePassword,
                decoration: InputDecoration(
                  labelText: "Password",
                  prefixIcon: const Icon(Icons.lock_outline_rounded, color: AppColors.primaryNavy),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                      color: AppColors.textSecondary,
                    ),
                    onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Timing Note
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.lightBlue.withOpacity(0.4),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.accentBlue.withOpacity(0.3)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline_rounded, color: AppColors.accentBlue, size: 18),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        "Attendance window: 7:00 PM – 8:00 PM daily. GPS & Facial recognition required.",
                        style: TextStyle(fontSize: 12, color: AppColors.secondaryNavy),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Login Button
              ElevatedButton(
                onPressed: auth.isLoading ? null : _submitLogin,
                child: auth.isLoading
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                      )
                    : const Text("Sign In"),
              ),
              const SizedBox(height: 24),

              // Demo quick test pills
              const Center(
                child: Text(
                  "Quick Demo Credentials",
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.textMuted),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  ActionChip(
                    avatar: const Icon(Icons.person, size: 16, color: AppColors.primaryNavy),
                    label: const Text("Student (Aravind)", style: TextStyle(fontSize: 11)),
                    onPressed: () {
                      _tabController.animateTo(0);
                      _usernameController.text = "711321104001";
                      _passwordController.text = "Student@123";
                    },
                  ),
                  const SizedBox(width: 8),
                  ActionChip(
                    avatar: const Icon(Icons.security, size: 16, color: AppColors.primaryNavy),
                    label: const Text("Staff (Warden)", style: TextStyle(fontSize: 11)),
                    onPressed: () {
                      _tabController.animateTo(1);
                      _usernameController.text = "staff@kpriet.ac.in";
                      _passwordController.text = "Staff@123";
                    },
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
