import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/student_provider.dart';
import '../../widgets/metric_card.dart';
import '../../widgets/status_badge.dart';

class StudentDashboardScreen extends StatefulWidget {
  const StudentDashboardScreen({super.key});

  @override
  State<StudentDashboardScreen> createState() => _StudentDashboardScreenState();
}

class _StudentDashboardScreenState extends State<StudentDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<StudentProvider>().fetchDashboard();
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final studentProv = context.watch<StudentProvider>();
    final data = studentProv.dashboardData;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Student Dashboard"),
        actions: [
          IconButton(
            icon: const Icon(Icons.analytics_outlined),
            tooltip: "Attendance Analytics",
            onPressed: () => Navigator.pushNamed(context, '/attendance-analytics'),
          ),
          IconButton(
            icon: const Icon(Icons.history_rounded),
            tooltip: "Attendance History",
            onPressed: () => Navigator.pushNamed(context, '/attendance-history'),
          ),
          IconButton(
            icon: const Icon(Icons.account_circle_outlined),
            tooltip: "My Profile",
            onPressed: () => Navigator.pushNamed(context, '/student-profile'),
          ),
        ],
      ),
      body: studentProv.isLoading && data == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () => context.read<StudentProvider>().fetchDashboard(),
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Welcome Card
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [AppColors.primaryNavy, AppColors.secondaryNavy],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.primaryNavy.withOpacity(0.25),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      "Welcome Back,",
                                      style: TextStyle(
                                        color: Colors.white.withOpacity(0.75),
                                        fontSize: 13,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      data?.name ?? auth.currentUser?.name ?? "Hostel Student",
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 20,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              CircleAvatar(
                                radius: 26,
                                backgroundColor: Colors.white24,
                                child: const Icon(Icons.person, color: Colors.white, size: 28),
                              ),
                            ],
                          ),
                          const SizedBox(height: 14),
                          Wrap(
                            spacing: 12,
                            runSpacing: 6,
                            children: [
                              _infoChip(Icons.badge, data?.registerNumber ?? auth.currentUser?.identifier ?? ""),
                              _infoChip(Icons.domain, data?.department ?? "KPRIET"),
                              _infoChip(Icons.bed, data?.hostelRoom ?? "Hostel Block"),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),

                    // Today's Attendance Banner Card
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(18),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  "TODAY'S ATTENDANCE",
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.textSecondary,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                                StatusBadge(status: data?.todayStatus ?? "PENDING"),
                              ],
                            ),
                            const SizedBox(height: 12),
                            if (data?.todayStatus == "PRESENT")
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: AppColors.presentGreenLight,
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.verified_rounded, color: AppColors.presentGreen),
                                    const SizedBox(width: 10),
                                    Expanded(
                                      child: Text(
                                        "Attendance verified at ${data?.todayAttendanceTime ?? 'Today'}. You are recorded present for today.",
                                        style: const TextStyle(
                                          color: AppColors.presentGreen,
                                          fontWeight: FontWeight.w600,
                                          fontSize: 13,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              )
                            else
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  Row(
                                    children: [
                                      const Icon(Icons.access_time_rounded, size: 16, color: AppColors.textSecondary),
                                      const SizedBox(width: 6),
                                      Text(
                                        "Window: ${data?.windowStart ?? '19:00'} - ${data?.windowEnd ?? '20:00'} (7 PM - 8 PM)",
                                        style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 16),
                                  ElevatedButton.icon(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: AppColors.accentBlue,
                                      padding: const EdgeInsets.symmetric(vertical: 14),
                                    ),
                                    icon: const Icon(Icons.fingerprint_rounded, size: 24),
                                    label: const Text(
                                      "Register Today's Attendance",
                                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                                    ),
                                    onPressed: () {
                                      Navigator.pushNamed(context, '/location-verification');
                                    },
                                  ),
                                ],
                              ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 18),

                    // Attendance Statistics Summary
                    Row(
                      children: [
                        Expanded(
                          child: MetricCard(
                            title: "Attendance Rate",
                            value: "${data?.attendancePercentage.toStringAsFixed(1) ?? '0.0'}%",
                            icon: Icons.pie_chart_rounded,
                            accentColor: AppColors.accentBlue,
                            subtitle: "Overall",
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: MetricCard(
                            title: "Total Present",
                            value: "${data?.totalPresentDays ?? 0}",
                            icon: Icons.check_circle_outline_rounded,
                            accentColor: AppColors.presentGreen,
                            subtitle: "Days",
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: MetricCard(
                            title: "Total Absent",
                            value: "${data?.totalAbsentDays ?? 0}",
                            icon: Icons.highlight_off_rounded,
                            accentColor: AppColors.absentRed,
                            subtitle: "Days",
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),

                    // Recent History Header
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          "Recent Attendance History",
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        TextButton(
                          onPressed: () => Navigator.pushNamed(context, '/attendance-history'),
                          child: const Text("View All"),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),

                    // Recent list
                    if (data == null || data.recentHistory.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppColors.dividerColor),
                        ),
                        child: const Center(
                          child: Text(
                            "No past attendance records found.",
                            style: TextStyle(color: AppColors.textMuted),
                          ),
                        ),
                      )
                    else
                      ListView.separated(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: data.recentHistory.take(5).length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, index) {
                          final rec = data.recentHistory[index];
                          return Card(
                            child: ListTile(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                              leading: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: rec.isPresent
                                      ? AppColors.presentGreenLight
                                      : AppColors.absentRedLight,
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Icon(
                                  rec.isPresent ? Icons.check : Icons.close,
                                  color: rec.isPresent ? AppColors.presentGreen : AppColors.absentRed,
                                  size: 20,
                                ),
                              ),
                              title: Text(
                                rec.attendanceDate,
                                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                              ),
                              subtitle: Text(
                                rec.isPresent
                                    ? "Verified at ${rec.attendanceTime} (${rec.distanceMeters.toStringAsFixed(0)}m)"
                                    : "Absent (Window Closed)",
                                style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                              ),
                              trailing: StatusBadge(status: rec.status, fontSize: 11),
                            ),
                          );
                        },
                      ),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _infoChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white12,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white70, size: 14),
          const SizedBox(width: 5),
          Text(
            label,
            style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500),
          ),
        ],
      ),
    );
  }
}
