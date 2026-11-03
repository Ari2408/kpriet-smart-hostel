import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/attendance_provider.dart';
import '../../providers/student_provider.dart';

class AttendanceSuccessScreen extends StatelessWidget {
  const AttendanceSuccessScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final attProv = context.watch<AttendanceProvider>();
    final sub = attProv.lastSubmission;

    return WillPopScope(
      onWillPop: () async {
        context.read<StudentProvider>().fetchDashboard();
        Navigator.pushReplacementNamed(context, '/student-dashboard');
        return false;
      },
      child: Scaffold(
        backgroundColor: Colors.white,
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Spacer(),

                // Animated Success Icon
                Center(
                  child: Container(
                    width: 90,
                    height: 90,
                    decoration: BoxDecoration(
                      color: AppColors.presentGreenLight,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.presentGreen.withOpacity(0.3),
                          blurRadius: 20,
                          spreadRadius: 4,
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.check_circle_rounded,
                      color: AppColors.presentGreen,
                      size: 60,
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                const Center(
                  child: Text(
                    "Attendance Successfully Registered!",
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 8),
                const Center(
                  child: Text(
                    "Your identity and physical campus presence have been verified.",
                    style: TextStyle(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 32),

                // Receipt Card
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.dividerColor),
                  ),
                  child: Column(
                    children: [
                      _detailRow("Student Name", sub?.studentName ?? "Student"),
                      const Divider(height: 20),
                      _detailRow("Register Number", sub?.registerNumber ?? "-"),
                      const Divider(height: 20),
                      _detailRow("Attendance Date", sub?.attendanceDate ?? "-"),
                      const Divider(height: 20),
                      _detailRow("Time of Verification", sub?.attendanceTime ?? "-"),
                      const Divider(height: 20),
                      _detailRow("Face Confidence", "${((sub?.faceConfidence ?? 0.95) * 100).toStringAsFixed(1)}%"),
                      const Divider(height: 20),
                      _detailRow("Geofence Distance", "${sub?.distanceFromCampus.toStringAsFixed(1) ?? '0.0'} m"),
                      const Divider(height: 20),
                      _detailRow(
                        "Status",
                        "PRESENT",
                        valueColor: AppColors.presentGreen,
                        isBold: true,
                      ),
                    ],
                  ),
                ),

                const Spacer(),

                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primaryNavy,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  onPressed: () {
                    context.read<StudentProvider>().fetchDashboard();
                    Navigator.pushReplacementNamed(context, '/student-dashboard');
                  },
                  child: const Text("Back to Dashboard"),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _detailRow(String label, String value, {Color? valueColor, bool isBold = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 13,
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w500,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: isBold ? FontWeight.w800 : FontWeight.w600,
            color: valueColor ?? AppColors.textPrimary,
          ),
        ),
      ],
    );
  }
}
