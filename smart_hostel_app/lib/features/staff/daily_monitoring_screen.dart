import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/status_badge.dart';

class DailyMonitoringScreen extends StatefulWidget {
  const DailyMonitoringScreen({super.key});

  @override
  State<DailyMonitoringScreen> createState() => _DailyMonitoringScreenState();
}

class _DailyMonitoringScreenState extends State<DailyMonitoringScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<StaffProvider>().fetchDashboard();
    });
  }

  @override
  Widget build(BuildContext context) {
    final staffProv = context.watch<StaffProvider>();
    final data = staffProv.dashboardData;
    final records = data?.records ?? [];

    final presentCount = data?.presentToday ?? 0;
    final totalCount = data?.totalStudents ?? 1;
    final rate = (presentCount / (totalCount == 0 ? 1 : totalCount)) * 100.0;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Daily Live Monitoring"),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => staffProv.fetchDashboard(),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Live Progress Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.dividerColor),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        "ATTENDANCE CHECK-IN PROGRESS",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.6,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.presentGreenLight,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          "${rate.toStringAsFixed(1)}% Completed",
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w800,
                            color: AppColors.presentGreen,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: LinearProgressIndicator(
                      value: (presentCount / (totalCount == 0 ? 1 : totalCount)).clamp(0.0, 1.0),
                      minHeight: 12,
                      backgroundColor: AppColors.surfaceMuted,
                      valueColor: const AlwaysStoppedAnimation<Color>(AppColors.presentGreen),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        "$presentCount / $totalCount Verified",
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                      ),
                      Text(
                        "${data?.pendingToday ?? 0} Pending • ${data?.absentToday ?? 0} Absent",
                        style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // Real-time verification stream
            const Text(
              "Live Student Check-in Feed",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 12),

            if (records.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Text("No records available for today.", style: TextStyle(color: AppColors.textMuted)),
                ),
              )
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: records.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  final r = records[index];
                  return Card(
                    child: ListTile(
                      leading: Icon(
                        r.isPresent ? Icons.verified_user_rounded : Icons.pending_rounded,
                        color: r.isPresent ? AppColors.presentGreen : AppColors.pendingOrange,
                      ),
                      title: Text(r.studentName, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                      subtitle: Text("${r.registerNumber} • Room ${r.hostelRoom}"),
                      trailing: StatusBadge(status: r.status, fontSize: 10),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }
}
