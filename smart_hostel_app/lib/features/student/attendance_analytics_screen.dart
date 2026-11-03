import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/student_provider.dart';
import '../../widgets/metric_card.dart';

class AttendanceAnalyticsScreen extends StatelessWidget {
  const AttendanceAnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final studentProv = context.watch<StudentProvider>();
    final data = studentProv.dashboardData;

    final percentage = data?.attendancePercentage ?? 0.0;
    final present = data?.totalPresentDays ?? 0;
    final absent = data?.totalAbsentDays ?? 0;
    final applicable = data?.totalApplicableDays ?? 0;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Attendance Analytics"),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Gauge & Percentage Card
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: AppColors.dividerColor),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.04),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                children: [
                  const Text(
                    "OVERALL ATTENDANCE PERCENTAGE",
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textSecondary,
                      letterSpacing: 0.8,
                    ),
                  ),
                  const SizedBox(height: 20),
                  Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox(
                        width: 150,
                        height: 150,
                        child: CircularProgressIndicator(
                          value: (percentage / 100.0).clamp(0.0, 1.0),
                          strokeWidth: 14,
                          backgroundColor: AppColors.surfaceMuted,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            percentage >= 75.0
                                ? AppColors.presentGreen
                                : percentage >= 60.0
                                    ? AppColors.pendingOrange
                                    : AppColors.absentRed,
                          ),
                        ),
                      ),
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            "${percentage.toStringAsFixed(1)}%",
                            style: const TextStyle(
                              fontSize: 32,
                              fontWeight: FontWeight.w900,
                              color: AppColors.textPrimary,
                              letterSpacing: -1,
                            ),
                          ),
                          Text(
                            percentage >= 75.0 ? "Eligible" : "Warning",
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: percentage >= 75.0 ? AppColors.presentGreen : AppColors.absentRed,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  // Formula Display
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceMuted,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      children: const [
                        Text(
                          "Institutional Calculation Formula:",
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.textSecondary),
                        ),
                        SizedBox(height: 4),
                        Text(
                          "Attendance % = (Present Days / Total Applicable Days) × 100",
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.primaryNavy),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // Statistics Row
            Row(
              children: [
                Expanded(
                  child: MetricCard(
                    title: "Present Days",
                    value: "$present",
                    icon: Icons.check_circle_rounded,
                    accentColor: AppColors.presentGreen,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: MetricCard(
                    title: "Absent Days",
                    value: "$absent",
                    icon: Icons.cancel_rounded,
                    accentColor: AppColors.absentRed,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: MetricCard(
                    title: "Applicable Days",
                    value: "$applicable",
                    icon: Icons.date_range_rounded,
                    accentColor: AppColors.accentBlue,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Monthly Breakdown Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      "Monthly Attendance Breakdown",
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
                    ),
                    const SizedBox(height: 16),
                    if (data == null || data.monthlySummary.isEmpty)
                      const Text(
                        "No monthly history accumulated yet.",
                        style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                      )
                    else
                      ...data.monthlySummary.entries.map((entry) {
                        final monthName = entry.key;
                        final stats = entry.value as Map<String, dynamic>;
                        final mPresent = stats['present'] ?? 0;
                        final mTotal = stats['total'] ?? 1;
                        final mRate = ((mPresent / (mTotal == 0 ? 1 : mTotal)) * 100).toStringAsFixed(1);

                        return Padding(
                          padding: const EdgeInsets.only(bottom: 14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    monthName,
                                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                                  ),
                                  Text(
                                    "$mRate% ($mPresent / $mTotal days)",
                                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: AppColors.primaryNavy),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(4),
                                child: LinearProgressIndicator(
                                  value: (mPresent / (mTotal == 0 ? 1 : mTotal)).clamp(0.0, 1.0),
                                  minHeight: 8,
                                  backgroundColor: AppColors.surfaceMuted,
                                  valueColor: const AlwaysStoppedAnimation<Color>(AppColors.presentGreen),
                                ),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Institutional Notice
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppColors.lightBlue.withOpacity(0.3),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.accentBlue.withOpacity(0.2)),
              ),
              child: const Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_rounded, color: AppColors.accentBlue, size: 20),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      "Official institutional policy: Approved gate passes, holidays, and college-declared non-working hostel days are strictly excluded from applicable attendance calculations.",
                      style: TextStyle(fontSize: 12, color: AppColors.secondaryNavy, height: 1.4),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
