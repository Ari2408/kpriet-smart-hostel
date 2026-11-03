import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/attendance_provider.dart';
import '../../providers/config_provider.dart';
import '../../widgets/campus_radar_widget.dart';

class LocationVerificationScreen extends StatefulWidget {
  const LocationVerificationScreen({super.key});

  @override
  State<LocationVerificationScreen> createState() => _LocationVerificationScreenState();
}

class _LocationVerificationScreenState extends State<LocationVerificationScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await context.read<ConfigProvider>().fetchConfig();
      if (mounted) {
        _triggerLocationCheck();
      }
    });
    _triggerLocationCheck();
  }

  void _triggerLocationCheck() {
    final config = context.read<ConfigProvider>().config;
    context.read<AttendanceProvider>().verifyLocation(
      campusLat: config?.campusLatitude,
      campusLon: config?.campusLongitude,
    );
  }

  @override
  Widget build(BuildContext context) {
    final attProv = context.watch<AttendanceProvider>();
    final config = context.watch<ConfigProvider>().config;
    final locResult = attProv.locationResult;
    final isInside = locResult?.insideGeofence ?? false;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Step 1: Geofence Verification"),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Progress indicator
              Row(
                children: [
                  _stepPill("1. GPS Geofence", isActive: true, isDone: isInside),
                  const SizedBox(width: 8),
                  const Icon(Icons.arrow_forward, size: 16, color: AppColors.textMuted),
                  const SizedBox(width: 8),
                  _stepPill("2. Face Verification", isActive: false, isDone: false),
                ],
              ),
              const SizedBox(height: 24),

              // Title & Instructions
              const Text(
                "Verifying Physical Campus Presence",
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                "Attendance can only be registered if you are physically within the KPR Institute of Engineering and Technology campus boundary.",
                style: TextStyle(
                  fontSize: 14,
                  color: AppColors.textSecondary,
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 24),

              // Radar Widget
              if (attProv.isVerifyingLocation)
                Expanded(
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: const [
                        CircularProgressIndicator(),
                        SizedBox(height: 20),
                        Text(
                          "Acquiring high-accuracy GPS fix...",
                          style: TextStyle(color: AppColors.textSecondary, fontWeight: FontWeight.w500),
                        ),
                      ],
                    ),
                  ),
                )
              else ...[
                CampusRadarWidget(
                  insideGeofence: isInside,
                  distanceMeters: locResult?.distanceMeters ?? -1.0,
                  radiusMeters: config?.geofenceRadiusMeters ?? 600.0,
                  campusName: config?.campusName ?? "KPRIET Campus",
                ),
                const SizedBox(height: 20),

                // Error / warning banner if outside
                if (locResult != null && !isInside)
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppColors.absentRedLight,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.absentRed.withOpacity(0.3)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.error_outline_rounded, color: AppColors.absentRed),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            locResult.message.isNotEmpty
                                ? locResult.message
                                : "You are outside the college campus. Attendance cannot be registered.",
                            style: const TextStyle(
                              color: AppColors.absentRed,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  )
                else if (attProv.errorMessage != null)
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppColors.absentRedLight,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      attProv.errorMessage!,
                      style: const TextStyle(color: AppColors.absentRed, fontSize: 13),
                    ),
                  ),

                const Spacer(),

                // Action buttons
                if (!isInside)
                  OutlinedButton.icon(
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text("Re-check GPS Location"),
                    onPressed: _triggerLocationCheck,
                  )
                else
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.presentGreen,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    icon: const Icon(Icons.camera_alt_rounded),
                    label: const Text(
                      "Proceed to Face Verification",
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                    onPressed: () {
                      Navigator.pushNamed(context, '/facial-recognition');
                    },
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _stepPill(String title, {required bool isActive, required bool isDone}) {
    Color bg = AppColors.surfaceMuted;
    Color fg = AppColors.textSecondary;
    if (isDone) {
      bg = AppColors.presentGreenLight;
      fg = AppColors.presentGreen;
    } else if (isActive) {
      bg = AppColors.lightBlue;
      fg = AppColors.accentBlue;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        title,
        style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}
