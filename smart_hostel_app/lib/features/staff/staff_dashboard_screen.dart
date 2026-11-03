import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/metric_card.dart';
import '../../widgets/status_badge.dart';

class StaffDashboardScreen extends StatefulWidget {
  const StaffDashboardScreen({super.key});

  @override
  State<StaffDashboardScreen> createState() => _StaffDashboardScreenState();
}

class _StaffDashboardScreenState extends State<StaffDashboardScreen> {
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<StaffProvider>().fetchDashboard();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final staffProv = context.watch<StaffProvider>();
    final data = staffProv.dashboardData;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Staff Attendance Console"),
        actions: [
          IconButton(
            icon: const Icon(Icons.people_alt_rounded),
            tooltip: "Manage Students",
            onPressed: () => Navigator.pushNamed(context, '/student-management'),
          ),
          IconButton(
            icon: const Icon(Icons.person_off_rounded),
            tooltip: "Absent Students",
            onPressed: () => Navigator.pushNamed(context, '/absent-students'),
          ),
          IconButton(
            icon: const Icon(Icons.picture_as_pdf_rounded),
            tooltip: "Reports & Export",
            onPressed: () => Navigator.pushNamed(context, '/reports'),
          ),
          IconButton(
            icon: const Icon(Icons.settings_rounded),
            tooltip: "Campus Geofence Settings",
            onPressed: () => Navigator.pushNamed(context, '/admin-settings'),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            tooltip: "Log Out",
            onPressed: () async {
              await context.read<AuthProvider>().logout();
              if (context.mounted) {
                Navigator.pushNamedAndRemoveUntil(context, '/login', (route) => false);
              }
            },
          ),
        ],
      ),
      body: staffProv.isLoading && data == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () => staffProv.fetchDashboard(),
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Institution & Window Status Card
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: AppColors.dividerColor),
                      ),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: AppColors.primaryNavy.withOpacity(0.08),
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.school, color: AppColors.primaryNavy, size: 20),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  "KPR Institute of Engineering and Technology",
                                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  "Window: ${data?.windowStart ?? '19:00'} - ${data?.windowEnd ?? '20:00'} • Server Time: ${data?.serverTime ?? ''}",
                                  style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: (data?.attendanceWindowOpen ?? false)
                                  ? AppColors.presentGreenLight
                                  : AppColors.surfaceMuted,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              (data?.attendanceWindowOpen ?? false) ? "WINDOW OPEN" : "CLOSED",
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w800,
                                color: (data?.attendanceWindowOpen ?? false)
                                    ? AppColors.presentGreen
                                    : AppColors.textMuted,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Metrics 4-grid
                    GridView.count(
                      crossAxisCount: 2,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      childAspectRatio: 1.45,
                      children: [
                        MetricCard(
                          title: "Total Students",
                          value: "${data?.totalStudents ?? 0}",
                          icon: Icons.groups_rounded,
                          accentColor: AppColors.primaryNavy,
                          onTap: () => Navigator.pushNamed(context, '/student-management'),
                        ),
                        MetricCard(
                          title: "Present Today",
                          value: "${data?.presentToday ?? 0}",
                          icon: Icons.check_circle_rounded,
                          accentColor: AppColors.presentGreen,
                        ),
                        MetricCard(
                          title: "Absent Today",
                          value: "${data?.absentToday ?? 0}",
                          icon: Icons.cancel_rounded,
                          accentColor: AppColors.absentRed,
                          subtitle: "Cutoff passed",
                          onTap: () => Navigator.pushNamed(context, '/absent-students'),
                        ),
                        MetricCard(
                          title: "Attendance Pending",
                          value: "${data?.pendingToday ?? 0}",
                          icon: Icons.hourglass_top_rounded,
                          accentColor: AppColors.pendingOrange,
                          subtitle: "Awaiting check",
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),

                    // Quick Actions
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.accentBlue,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                            icon: const Icon(Icons.person_add_rounded, size: 18),
                            label: const Text("Add Student", style: TextStyle(fontSize: 13)),
                            onPressed: () => Navigator.pushNamed(context, '/add-student'),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: OutlinedButton.icon(
                            style: OutlinedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                            icon: const Icon(Icons.picture_as_pdf_rounded, size: 18),
                            label: const Text("Export Reports", style: TextStyle(fontSize: 13)),
                            onPressed: () => Navigator.pushNamed(context, '/reports'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),

                    // Search and Filter Bar
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          children: [
                            TextField(
                              controller: _searchController,
                              decoration: InputDecoration(
                                hintText: "Search student by name or register number...",
                                prefixIcon: const Icon(Icons.search_rounded, size: 20),
                                suffixIcon: _searchController.text.isNotEmpty
                                    ? IconButton(
                                        icon: const Icon(Icons.clear, size: 18),
                                        onPressed: () {
                                          _searchController.clear();
                                          staffProv.setSearchQuery("");
                                        },
                                      )
                                    : null,
                                contentPadding: const EdgeInsets.symmetric(vertical: 10),
                              ),
                              onSubmitted: (val) => staffProv.setSearchQuery(val),
                            ),
                            const SizedBox(height: 12),
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: Row(
                                children: [
                                  _filterPill("ALL", "All Students", staffProv),
                                  const SizedBox(width: 8),
                                  _filterPill("PRESENT", "Present", staffProv),
                                  const SizedBox(width: 8),
                                  _filterPill("ABSENT", "Absent", staffProv),
                                  const SizedBox(width: 8),
                                  _filterPill("PENDING", "Pending", staffProv),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Students Attendance List Table
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          "Today's Live Roster",
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
                        ),
                        Text(
                          "${data?.records.length ?? 0} students listed",
                          style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),

                    if (data == null || data.records.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(32),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppColors.dividerColor),
                        ),
                        child: const Center(
                          child: Text(
                            "No student records match the selected filter.",
                            style: TextStyle(color: AppColors.textMuted),
                          ),
                        ),
                      )
                    else
                      ListView.separated(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: data.records.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          final r = data.records[index];
                          return Card(
                            child: ListTile(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              leading: CircleAvatar(
                                backgroundColor: r.isPresent
                                    ? AppColors.presentGreenLight
                                    : r.isAbsent
                                        ? AppColors.absentRedLight
                                        : AppColors.pendingOrangeLight,
                                child: Text(
                                  r.studentName.isNotEmpty ? r.studentName[0] : "S",
                                  style: TextStyle(
                                    fontWeight: FontWeight.w800,
                                    color: r.isPresent
                                        ? AppColors.presentGreen
                                        : r.isAbsent
                                            ? AppColors.absentRed
                                            : AppColors.pendingOrange,
                                  ),
                                ),
                              ),
                              title: Text(
                                r.studentName,
                                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const SizedBox(height: 2),
                                  Text(
                                    "${r.registerNumber} • ${r.department}",
                                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    "Room: ${r.hostelRoom} ${r.isPresent ? '• ' + r.attendanceTime : ''}",
                                    style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                                  ),
                                ],
                              ),
                              trailing: StatusBadge(status: r.status, fontSize: 11),
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

  Widget _filterPill(String key, String label, StaffProvider prov) {
    final isSelected = prov.statusFilter == key;
    return ChoiceChip(
      selected: isSelected,
      label: Text(label),
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
        color: isSelected ? Colors.white : AppColors.textPrimary,
      ),
      selectedColor: AppColors.primaryNavy,
      backgroundColor: AppColors.surfaceMuted,
      onSelected: (_) => prov.setStatusFilter(key),
    );
  }
}
