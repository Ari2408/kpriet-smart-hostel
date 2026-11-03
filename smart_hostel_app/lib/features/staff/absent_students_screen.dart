import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/status_badge.dart';

class AbsentStudentsScreen extends StatefulWidget {
  const AbsentStudentsScreen({super.key});

  @override
  State<AbsentStudentsScreen> createState() => _AbsentStudentsScreenState();
}

class _AbsentStudentsScreenState extends State<AbsentStudentsScreen> {
  String _selectedDept = "All";

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<StaffProvider>().fetchAbsentees();
    });
  }

  @override
  Widget build(BuildContext context) {
    final staffProv = context.watch<StaffProvider>();
    final absentees = staffProv.absentees;

    final filtered = absentees.where((s) {
      if (_selectedDept == "All") return true;
      return s.department == _selectedDept;
    }).toList();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Absent & Unregistered Students"),
      ),
      body: Column(
        children: [
          // Banner explanation
          Container(
            padding: const EdgeInsets.all(14),
            color: AppColors.surfaceMuted,
            child: Row(
              children: [
                const Icon(Icons.info_outline_rounded, color: AppColors.secondaryNavy, size: 20),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    "Showing students who have not registered attendance for today. Students are marked Pending during window and Absent after 8:00 PM cutoff.",
                    style: const TextStyle(fontSize: 12, color: AppColors.secondaryNavy),
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),

          // Department selector
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: Colors.white,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  "All",
                  "Computer Science & Engineering",
                  "Artificial Intelligence & Data Science",
                  "Electronics & Communication Engineering",
                  "Mechanical Engineering"
                ].map((dept) {
                  final isSel = _selectedDept == dept;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      selected: isSel,
                      label: Text(dept == "All" ? "All Departments" : dept.split("&").first.trim()),
                      labelStyle: TextStyle(
                        fontSize: 11,
                        color: isSel ? Colors.white : AppColors.textPrimary,
                        fontWeight: isSel ? FontWeight.w700 : FontWeight.w500,
                      ),
                      selectedColor: AppColors.primaryNavy,
                      backgroundColor: AppColors.surfaceMuted,
                      onSelected: (_) => setState(() => _selectedDept = dept),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          const Divider(height: 1),

          // List of absentees
          Expanded(
            child: staffProv.isLoading && absentees.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : filtered.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: const [
                            Icon(Icons.check_circle_outline_rounded, size: 64, color: AppColors.presentGreen),
                            SizedBox(height: 12),
                            Text(
                              "All students have registered today!",
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: AppColors.presentGreen,
                              ),
                            ),
                            SizedBox(height: 4),
                            Text(
                              "Zero absentees in the selected department.",
                              style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                            ),
                          ],
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: () => staffProv.fetchAbsentees(department: _selectedDept),
                        child: ListView.separated(
                          padding: const EdgeInsets.all(16),
                          itemCount: filtered.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 10),
                          itemBuilder: (context, index) {
                            final s = filtered[index];
                            return Card(
                              child: Padding(
                                padding: const EdgeInsets.all(14),
                                child: Row(
                                  children: [
                                    CircleAvatar(
                                      radius: 24,
                                      backgroundColor: AppColors.absentRedLight,
                                      child: Text(
                                        s.name.isNotEmpty ? s.name[0] : "A",
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w800,
                                          color: AppColors.absentRed,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 14),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            s.name,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w700,
                                              fontSize: 15,
                                              color: AppColors.textPrimary,
                                            ),
                                          ),
                                          const SizedBox(height: 2),
                                          Text(
                                            "Reg: ${s.registerNumber} • Year ${s.academicYear}",
                                            style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                                          ),
                                          const SizedBox(height: 2),
                                          Text(
                                            "Hostel: ${s.hostelBlock} ${s.roomNumber}",
                                            style: const TextStyle(
                                              fontSize: 12,
                                              color: AppColors.primaryNavy,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      children: [
                                        StatusBadge(status: s.status, fontSize: 10),
                                        const SizedBox(height: 8),
                                        if (s.phoneNumber != null)
                                          Text(
                                            s.phoneNumber!,
                                            style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                                          ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }
}
