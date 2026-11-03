import 'dart:io';
import 'package:flutter/material.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:path_provider/path_provider.dart';
import '../models/attendance_model.dart';

class PdfCsvService {
  static Future<void> printOrSharePdf({
    required List<AttendanceRecordItem> records,
    required String campusName,
    required String reportTitle,
    required BuildContext context,
  }) async {
    final doc = pw.Document();

    final presentCount = records.where((r) => r.isPresent).length;
    final absentCount = records.where((r) => r.isAbsent).length;
    final rate = records.isEmpty ? 0.0 : (presentCount / records.length) * 100.0;

    doc.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(32),
        build: (pw.Context context) {
          return [
            pw.Center(
              child: pw.Text(
                campusName.toUpperCase(),
                style: pw.TextStyle(
                  fontSize: 16,
                  fontWeight: pw.FontWeight.bold,
                  color: PdfColors.blue900,
                ),
              ),
            ),
            pw.SizedBox(height: 4),
            pw.Center(
              child: pw.Text(
                "Smart Hostel Attendance System - $reportTitle",
                style: pw.TextStyle(fontSize: 12, color: PdfColors.grey700),
              ),
            ),
            pw.SizedBox(height: 14),

            // Summary box
            pw.Container(
              padding: const pw.EdgeInsets.all(10),
              decoration: pw.BoxDecoration(
                border: pw.Border.all(color: PdfColors.grey400),
                borderRadius: pw.BorderRadius.circular(6),
                color: PdfColors.grey100,
              ),
              child: pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.spaceAround,
                children: [
                  pw.Text("Total: ${records.length}"),
                  pw.Text("Present: $presentCount", style: pw.TextStyle(color: PdfColors.green800)),
                  pw.Text("Absent: $absentCount", style: pw.TextStyle(color: PdfColors.red800)),
                  pw.Text("Rate: ${rate.toStringAsFixed(1)}%"),
                ],
              ),
            ),
            pw.SizedBox(height: 14),

            // Table
            pw.TableHelper.fromTextArray(
              context: context,
              headers: ["Reg No", "Student Name", "Dept", "Room", "Date", "Time", "Status"],
              data: records.map((r) => [
                r.registerNumber.length > 8 ? r.registerNumber.substring(r.registerNumber.length - 8) : r.registerNumber,
                r.studentName,
                r.department,
                r.hostelRoom,
                r.attendanceDate,
                r.attendanceTime,
                r.status,
              ]).toList(),
              headerStyle: pw.TextStyle(
                fontWeight: pw.FontWeight.bold,
                color: PdfColors.white,
                fontSize: 9,
              ),
              headerDecoration: const pw.BoxDecoration(color: PdfColors.blue900),
              cellStyle: const pw.TextStyle(fontSize: 8),
              cellAlignment: pw.Alignment.center,
              cellPadding: const pw.EdgeInsets.symmetric(horizontal: 4, vertical: 4),
            ),
          ];
        },
      ),
    );

    await Printing.layoutPdf(
      onLayout: (PdfPageFormat format) async => doc.save(),
      name: "Hostel_Attendance_Report.pdf",
    );
  }

  static Future<String> saveCsvLocally(List<AttendanceRecordItem> records) async {
    final StringBuffer csvBuffer = StringBuffer();
    csvBuffer.writeln("Record ID,Student Name,Register Number,Department,Room,Date,Time,Status,Distance (m),Face Confidence (%)");

    for (var r in records) {
      csvBuffer.writeln(
        "${r.id},\"${r.studentName}\",\"${r.registerNumber}\",\"${r.department}\",\"${r.hostelRoom}\",\"${r.attendanceDate}\",\"${r.attendanceTime}\",\"${r.status}\",${r.distanceMeters.toStringAsFixed(1)},${(r.faceConfidence * 100).toStringAsFixed(1)}"
      );
    }

    final directory = await getApplicationDocumentsDirectory();
    final file = File("${directory.path}/Hostel_Attendance_${DateTime.now().millisecondsSinceEpoch}.csv");
    await file.writeAsString(csvBuffer.toString());
    return file.path;
  }
}
