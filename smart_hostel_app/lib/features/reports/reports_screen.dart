import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/constants/api_constants.dart';
import '../../core/theme/app_theme.dart';
import '../../models/attendance_model.dart';
import '../../providers/config_provider.dart';
import '../../services/api_service.dart';
import '../../services/pdf_csv_service.dart';
import '../../widgets/metric_card.dart';

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  Map<String, dynamic>? _summary;
  List<AttendanceRecordItem> _records = [];
  bool _isLoading = true;
  String _selectedDept = "All";
  bool _isExporting = false;

  final List<String> _departments = [
    "All",
    "Computer Science & Engineering",
    "Artificial Intelligence & Data Science",
    "Electronics & Communication Engineering",
    "Mechanical Engineering",
  ];

  @override
  void initState() {
    super.initState();
    _fetchReportsData();
  }

  Future<void> _fetchReportsData() async {
    setState(() => _isLoading = true);
    try {
      final summaryRes = await ApiService.get(
        _selectedDept == "All"
            ? ApiConstants.reportsSummaryUrl
            : "${ApiConstants.reportsSummaryUrl}?department=${Uri.encodeComponent(_selectedDept)}",
      );

      final historyRes = await ApiService.get(
        _selectedDept == "All"
            ? ApiConstants.historyUrl
            : "${ApiConstants.historyUrl}?department=${Uri.encodeComponent(_selectedDept)}",
      );

      List<AttendanceRecordItem> recordList = [];
      if (historyRes is List) {
        recordList = historyRes.map((r) => AttendanceRecordItem.fromJson(r)).toList();
      }

      setState(() {
        _summary = summaryRes;
        _records = recordList;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error fetching reports: ${e.toString()}")),
      );
    }
  }

  void _exportPdf() async {
    setState(() => _isExporting = true);
    final campus = context.read<ConfigProvider>().config?.campusName ?? "KPR Institute of Engineering and Technology";

    try {
      await PdfCsvService.printOrSharePdf(
        records: _records,
        campusName: campus,
        reportTitle: _selectedDept == "All" ? "Institutional Attendance Report" : "$_selectedDept Report",
        context: context,
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("PDF generation error: ${e.toString()}")),
      );
    } finally {
      setState(() => _isExporting = false);
    }
  }

  void _exportCsv() async {
    setState(() => _isExporting = true);
    try {
      final filePath = await PdfCsvService.saveCsvLocally(_records);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("CSV successfully generated:\n$filePath"),
            backgroundColor: AppColors.presentGreen,
            duration: const Duration(seconds: 4),
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("CSV export error: ${e.toString()}")),
      );
    } finally {
      setState(() => _isExporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final present = _summary?["total_present"] ?? 0;
    final absent = _summary?["total_absent"] ?? 0;
    final rate = (_summary?["attendance_rate_percentage"] as num?)?.toDouble() ?? 0.0;
    final deptBreakdown = _summary?["department_breakdown"] as Map<String, dynamic>? ?? {};

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Attendance Reports"),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Department Dropdown filter
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.dividerColor),
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: _selectedDept,
                        isExpanded: true,
                        icon: const Icon(Icons.filter_list_rounded, color: AppColors.primaryNavy),
                        items: _departments.map((d) => DropdownMenuItem(value: d, child: Text(d))).toList(),
                        onChanged: (val) {
                          if (val != null) {
                            setState(() => _selectedDept = val);
                            _fetchReportsData();
                          }
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),

                  // Overall Summary Row
                  Row(
                    children: [
                      Expanded(
                        child: MetricCard(
                          title: "Attendance Rate",
                          value: "${rate.toStringAsFixed(1)}%",
                          icon: Icons.pie_chart_rounded,
                          accentColor: AppColors.accentBlue,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: MetricCard(
                          title: "Total Present",
                          value: "$present",
                          icon: Icons.check_circle_rounded,
                          accentColor: AppColors.presentGreen,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: MetricCard(
                          title: "Total Absent",
                          value: "$absent",
                          icon: Icons.cancel_rounded,
                          accentColor: AppColors.absentRed,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // Export Action Buttons
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            "EXPORT OPTIONS",
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: AppColors.textSecondary,
                              letterSpacing: 0.6,
                            ),
                          ),
                          const SizedBox(height: 14),
                          Row(
                            children: [
                              Expanded(
                                child: ElevatedButton.icon(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.primaryNavy,
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                  ),
                                  icon: const Icon(Icons.picture_as_pdf_rounded, size: 20),
                                  label: const Text("Export PDF", style: TextStyle(fontSize: 14)),
                                  onPressed: _isExporting ? null : _exportPdf,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: OutlinedButton.icon(
                                  style: OutlinedButton.styleFrom(
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                  ),
                                  icon: const Icon(Icons.table_chart_rounded, size: 20),
                                  label: const Text("Export CSV", style: TextStyle(fontSize: 14)),
                                  onPressed: _isExporting ? null : _exportCsv,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Department Breakdown
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            "Department-wise Statistics",
                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
                          ),
                          const SizedBox(height: 14),
                          if (deptBreakdown.isEmpty)
                            const Text("No department data available.", style: TextStyle(color: AppColors.textMuted))
                          else
                            ...deptBreakdown.entries.map((e) {
                              final dName = e.key;
                              final dData = e.value as Map<String, dynamic>;
                              final dPres = dData["present"] ?? 0;
                              final dTot = dData["total"] ?? 1;
                              final dRate = ((dPres / (dTot == 0 ? 1 : dTot)) * 100).toStringAsFixed(1);

                              return Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Expanded(
                                          child: Text(
                                            dName,
                                            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                          ),
                                        ),
                                        Text(
                                          "$dRate% ($dPres / $dTot)",
                                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12, color: AppColors.primaryNavy),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 4),
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(4),
                                      child: LinearProgressIndicator(
                                        value: (dPres / (dTot == 0 ? 1 : dTot)).clamp(0.0, 1.0),
                                        minHeight: 6,
                                        backgroundColor: AppColors.surfaceMuted,
                                        valueColor: const AlwaysStoppedAnimation<Color>(AppColors.accentBlue),
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
                ],
              ),
            ),
    );
  }
}
