import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/constants/api_constants.dart';
import '../../core/theme/app_theme.dart';
import '../../models/user_model.dart';
import '../../providers/staff_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/metric_card.dart';

class StudentDetailScreen extends StatefulWidget {
  final UserModel student;

  const StudentDetailScreen({super.key, required this.student});

  @override
  State<StudentDetailScreen> createState() => _StudentDetailScreenState();
}

class _StudentDetailScreenState extends State<StudentDetailScreen> {
  Map<String, dynamic>? _stats;
  bool _isLoadingStats = true;

  @override
  void initState() {
    super.initState();
    _fetchStats();
  }

  Future<void> _fetchStats() async {
    try {
      final res = await ApiService.get(ApiConstants.studentDetailUrl(widget.student.id));
      if (res is Map && res.containsKey("statistics")) {
        setState(() {
          _stats = res["statistics"];
          _isLoadingStats = false;
        });
      }
    } catch (_) {
      setState(() => _isLoadingStats = false);
    }
  }

  void _showDeleteStudentDialog() {
    final confirmController = TextEditingController();
    final expectedRegNo = widget.student.identifier;
    bool isMatch = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) {
          return AlertDialog(
            icon: const Icon(Icons.warning_amber_rounded, color: AppColors.absentRed, size: 48),
            title: const Text(
              "Permanently Delete Student",
              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  "Are you sure you want to permanently delete this student? This action cannot be undone.",
                  style: TextStyle(
                    fontSize: 14,
                    color: AppColors.absentRed,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  "This will permanently purge biometric photos, facial feature embeddings, and authentication credentials. Historical attendance records will be anonymized for institutional audit compliance.",
                  style: TextStyle(fontSize: 12, color: AppColors.textSecondary, height: 1.4),
                ),
                const SizedBox(height: 16),
                Text(
                  "Type the register number $expectedRegNo to confirm:",
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: confirmController,
                  decoration: InputDecoration(
                    hintText: expectedRegNo,
                    border: const OutlineInputBorder(),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                  onChanged: (val) {
                    setDialogState(() {
                      isMatch = val.trim() == expectedRegNo.trim();
                    });
                  },
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text("Cancel"),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.absentRed,
                  disabledBackgroundColor: Colors.grey.shade300,
                ),
                onPressed: !isMatch
                    ? null
                    : () async {
                        Navigator.pop(ctx);
                        final staffProv = context.read<StaffProvider>();
                        final success = await staffProv.deleteStudentPermanently(
                          widget.student.id,
                          confirmController.text.trim(),
                        );

                        if (mounted) {
                          if (success) {
                            Navigator.pop(context); // Back to student list
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  "Student ${widget.student.name} (${widget.student.identifier}) has been permanently deleted.",
                                ),
                                backgroundColor: AppColors.absentRed,
                                duration: const Duration(seconds: 4),
                              ),
                            );
                          } else {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(staffProv.errorMessage ?? "Deletion failed"),
                                backgroundColor: AppColors.absentRed,
                              ),
                            );
                          }
                        }
                      },
                child: const Text("Delete Permanently", style: TextStyle(color: Colors.white)),
              ),
            ],
          );
        },
      ),
    );
  }

  void _showResetPasswordDialog() {
    final newPassController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text("Reset Password for ${widget.student.name}"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Configure a new initial password. Existing passwords are never displayed for security.",
              style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: newPassController,
              decoration: const InputDecoration(
                labelText: "New Password",
                hintText: "Min 8 characters",
                prefixIcon: Icon(Icons.lock_outline),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("Cancel")),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.primaryNavy),
            onPressed: () async {
              if (newPassController.text.length < 6) return;
              Navigator.pop(ctx);
              final staffProv = context.read<StaffProvider>();
              final ok = await staffProv.resetStudentPassword(widget.student.id, newPassController.text);
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(ok ? "Password reset successfully" : (staffProv.errorMessage ?? "Reset failed")),
                    backgroundColor: ok ? AppColors.presentGreen : AppColors.absentRed,
                  ),
                );
              }
            },
            child: const Text("Reset Password"),
          ),
        ],
      ),
    );
  }

  void _showEditStudentPlaceholder() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Edit Student Details"),
        content: Text("Editing profile for ${widget.student.name} (${widget.student.identifier})."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("Close")),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.student;
    final percentage = (_stats?["percentage"] as num?)?.toDouble() ?? 0.0;
    final present = _stats?["present_count"] ?? 0;
    final absent = _stats?["absent_count"] ?? 0;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(s.name),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_forever_rounded, color: Colors.white),
            tooltip: "Delete Student",
            onPressed: _showDeleteStudentDialog,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Student Profile Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    CircleAvatar(
                      radius: 40,
                      backgroundColor: AppColors.primaryNavy,
                      backgroundImage: s.profilePhotoUrl != null && s.profilePhotoUrl!.isNotEmpty
                          ? NetworkImage("${ApiConstants.baseUrl}${s.profilePhotoUrl}")
                          : null,
                      child: s.profilePhotoUrl == null || s.profilePhotoUrl!.isEmpty
                          ? Text(
                              s.name.isNotEmpty ? s.name[0] : "S",
                              style: const TextStyle(fontSize: 32, color: Colors.white, fontWeight: FontWeight.bold),
                            )
                          : null,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      s.name,
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      "Register Number: ${s.identifier}",
                      style: const TextStyle(fontSize: 14, color: AppColors.primaryNavy, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _chip(s.department ?? "Engineering"),
                        const SizedBox(width: 8),
                        _chip("Academic Year ${s.academicYear ?? 1}"),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Quick Actions: Edit Student & Delete Student
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      side: const BorderSide(color: AppColors.primaryNavy),
                    ),
                    icon: const Icon(Icons.edit_rounded, size: 18, color: AppColors.primaryNavy),
                    label: const Text("Edit Student", style: TextStyle(color: AppColors.primaryNavy, fontWeight: FontWeight.w700)),
                    onPressed: _showEditStudentPlaceholder,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      side: const BorderSide(color: AppColors.absentRed),
                    ),
                    icon: const Icon(Icons.delete_forever_rounded, size: 18, color: AppColors.absentRed),
                    label: const Text("Delete Student", style: TextStyle(color: AppColors.absentRed, fontWeight: FontWeight.w700)),
                    onPressed: _showDeleteStudentDialog,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextButton.icon(
              icon: const Icon(Icons.lock_reset_rounded, size: 18),
              label: const Text("Reset Student Password"),
              onPressed: _showResetPasswordDialog,
            ),
            const SizedBox(height: 14),

            // Attendance Statistics
            const Text(
              "Attendance Performance",
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: MetricCard(
                    title: "Rate",
                    value: _isLoadingStats ? "..." : "${percentage.toStringAsFixed(1)}%",
                    icon: Icons.pie_chart_rounded,
                    accentColor: AppColors.accentBlue,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: MetricCard(
                    title: "Present",
                    value: _isLoadingStats ? "..." : "$present",
                    icon: Icons.check_circle_rounded,
                    accentColor: AppColors.presentGreen,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: MetricCard(
                    title: "Absent",
                    value: _isLoadingStats ? "..." : "$absent",
                    icon: Icons.cancel_rounded,
                    accentColor: AppColors.absentRed,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Personal and Hostel Details
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      "HOSTEL & ACADEMIC INFORMATION",
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 12),
                    _detailItem("Hostel Block", s.hostelBlock ?? "Emerald Block"),
                    const Divider(height: 18),
                    _detailItem("Room Number", s.roomNumber ?? "B-201"),
                    const Divider(height: 18),
                    _detailItem("Academic Year", "Year ${s.academicYear ?? 1}"),
                    const Divider(height: 18),
                    _detailItem("Department", s.department ?? "Engineering"),
                    const Divider(height: 18),
                    _detailItem("Contact Phone", s.phoneNumber ?? "+91 98765 43210"),
                    const Divider(height: 18),
                    _detailItem("Email Address", s.email ?? "${s.identifier}@kpriet.ac.in"),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surfaceMuted,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.primaryNavy),
      ),
    );
  }

  Widget _detailItem(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
        Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
      ],
    );
  }
}
