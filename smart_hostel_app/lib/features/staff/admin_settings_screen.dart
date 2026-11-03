import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/constants/api_constants.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/config_provider.dart';
import '../../providers/staff_provider.dart';

class AdminSettingsScreen extends StatefulWidget {
  const AdminSettingsScreen({super.key});

  @override
  State<AdminSettingsScreen> createState() => _AdminSettingsScreenState();
}

class _AdminSettingsScreenState extends State<AdminSettingsScreen> {
  final _formKey = GlobalKey<FormState>();

  final _campusNameController = TextEditingController();
  final _latitudeController = TextEditingController();
  final _longitudeController = TextEditingController();
  final _radiusController = TextEditingController();
  final _startTimeController = TextEditingController();
  final _endTimeController = TextEditingController();
  final _serverUrlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadConfigValues();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await context.read<ConfigProvider>().fetchConfig();
      if (mounted) {
        _loadConfigValues();
      }
    });
  }

  void _loadConfigValues() {
    final config = context.read<ConfigProvider>().config;
    _campusNameController.text = config?.campusName ?? ApiConstants.defaultCampusName;
    _latitudeController.text = (config?.campusLatitude ?? ApiConstants.defaultCampusLat).toString();
    _longitudeController.text = (config?.campusLongitude ?? ApiConstants.defaultCampusLon).toString();
    _radiusController.text = (config?.geofenceRadiusMeters ?? ApiConstants.defaultRadiusMeters).toStringAsFixed(0);
    _startTimeController.text = config?.attendanceStartTime ?? ApiConstants.defaultStartTime;
    _endTimeController.text = config?.attendanceEndTime ?? ApiConstants.defaultEndTime;
    _serverUrlController.text = ApiConstants.baseUrl;
  }

  @override
  void dispose() {
    _campusNameController.dispose();
    _latitudeController.dispose();
    _longitudeController.dispose();
    _radiusController.dispose();
    _startTimeController.dispose();
    _endTimeController.dispose();
    _serverUrlController.dispose();
    super.dispose();
  }

  void _saveSettings() async {
    if (!_formKey.currentState!.validate()) return;

    final name = _campusNameController.text.trim();
    final lat = double.tryParse(_latitudeController.text.trim()) ?? ApiConstants.defaultCampusLat;
    final lon = double.tryParse(_longitudeController.text.trim()) ?? ApiConstants.defaultCampusLon;
    final radius = double.tryParse(_radiusController.text.trim()) ?? ApiConstants.defaultRadiusMeters;
    final start = _startTimeController.text.trim();
    final end = _endTimeController.text.trim();

    final timeRegex = RegExp(r'^([01]?\d|2[0-3]):[0-5]\d$');
    if (!timeRegex.hasMatch(start)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Start time must be in 24-hour HH:MM format (e.g. 19:00)."),
          backgroundColor: AppColors.absentRed,
        ),
      );
      return;
    }
    if (!timeRegex.hasMatch(end)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("End time must be in 24-hour HH:MM format (e.g. 20:00)."),
          backgroundColor: AppColors.absentRed,
        ),
      );
      return;
    }

    // Update backend base URL if edited
    if (_serverUrlController.text.trim().isNotEmpty) {
      context.read<AuthProvider>().updateBackendUrl(_serverUrlController.text.trim());
    }

    final configProv = context.read<ConfigProvider>();
    final success = await configProv.updateConfig(
      campusName: name,
      campusLatitude: lat,
      campusLongitude: lon,
      geofenceRadiusMeters: radius,
      attendanceStartTime: start,
      attendanceEndTime: end,
    );

    if (!mounted) return;

    if (success) {
      context.read<StaffProvider>().fetchDashboard();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Campus geofence and attendance window updated successfully!"),
          backgroundColor: AppColors.presentGreen,
        ),
      );
      Navigator.pop(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(configProv.errorMessage ?? "Failed to update configuration"),
          backgroundColor: AppColors.absentRed,
        ),
      );
    }
  }

  void _resetToKprietDefaults() {
    setState(() {
      _campusNameController.text = ApiConstants.defaultCampusName;
      _latitudeController.text = ApiConstants.defaultCampusLat.toString();
      _longitudeController.text = ApiConstants.defaultCampusLon.toString();
      _radiusController.text = ApiConstants.defaultRadiusMeters.toStringAsFixed(0);
      _startTimeController.text = ApiConstants.defaultStartTime;
      _endTimeController.text = ApiConstants.defaultEndTime;
    });
  }

  @override
  Widget build(BuildContext context) {
    final configProv = context.watch<ConfigProvider>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Campus Geofence Settings"),
        actions: [
          TextButton(
            onPressed: _resetToKprietDefaults,
            child: const Text("Reset KPRIET", style: TextStyle(color: Colors.white, fontSize: 13)),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Notice banner
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.lightBlue.withOpacity(0.4),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.accentBlue.withOpacity(0.3)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.tune_rounded, color: AppColors.primaryNavy),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        "Configure official GPS coordinates, boundary radius, and the 7 PM - 8 PM attendance window for KPR Institute of Engineering and Technology.",
                        style: TextStyle(fontSize: 12, color: AppColors.secondaryNavy),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              // Geofence Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "CAMPUS GEOFENCE PARAMETERS",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _campusNameController,
                        decoration: const InputDecoration(labelText: "Institution / Campus Name"),
                        validator: (v) => (v == null || v.trim().isEmpty) ? "Campus name required" : null,
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              controller: _latitudeController,
                              decoration: const InputDecoration(labelText: "Latitude", hintText: "11.05445"),
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              validator: (v) {
                                if (v == null || v.trim().isEmpty) return "Required";
                                final d = double.tryParse(v);
                                if (d == null || d < -90 || d > 90) return "Invalid";
                                return null;
                              },
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextFormField(
                              controller: _longitudeController,
                              decoration: const InputDecoration(labelText: "Longitude", hintText: "77.08641"),
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              validator: (v) {
                                if (v == null || v.trim().isEmpty) return "Required";
                                final d = double.tryParse(v);
                                if (d == null || d < -180 || d > 180) return "Invalid";
                                return null;
                              },
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _radiusController,
                        decoration: const InputDecoration(
                          labelText: "Allowed Geofence Radius (meters)",
                          hintText: "e.g. 600",
                          suffixText: "meters",
                        ),
                        keyboardType: TextInputType.number,
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) return "Radius required";
                          final r = double.tryParse(v);
                          if (r == null || r <= 0) return "Must be > 0";
                          return null;
                        },
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 18),

              // Timing Window Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "ATTENDANCE TIME WINDOW",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              controller: _startTimeController,
                              decoration: const InputDecoration(
                                labelText: "Start Time (24h)",
                                hintText: "19:00",
                                prefixIcon: Icon(Icons.access_time_rounded),
                              ),
                              validator: (v) => (v == null || !v.contains(":")) ? "Format HH:MM" : null,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextFormField(
                              controller: _endTimeController,
                              decoration: const InputDecoration(
                                labelText: "Closing Time (24h)",
                                hintText: "20:00",
                                prefixIcon: Icon(Icons.lock_clock_rounded),
                              ),
                              validator: (v) => (v == null || !v.contains(":")) ? "Format HH:MM" : null,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 18),

              // Server URL Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "BACKEND REST API ENDPOINT",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _serverUrlController,
                        decoration: const InputDecoration(
                          labelText: "Server Base URL",
                          hintText: ApiConstants.productionBaseUrl,
                          prefixIcon: Icon(Icons.dns_rounded),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryNavy,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                onPressed: configProv.isLoading ? null : _saveSettings,
                child: configProv.isLoading
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                      )
                    : const Text("Save System Configuration", style: TextStyle(fontSize: 16)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
