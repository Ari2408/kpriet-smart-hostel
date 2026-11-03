import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:smart_hostel_app/core/theme/app_theme.dart';
import 'package:smart_hostel_app/features/authentication/login_screen.dart';
import 'package:smart_hostel_app/providers/auth_provider.dart';
import 'package:smart_hostel_app/providers/student_provider.dart';
import 'package:smart_hostel_app/providers/staff_provider.dart';
import 'package:smart_hostel_app/providers/attendance_provider.dart';
import 'package:smart_hostel_app/providers/config_provider.dart';

void main() {
  testWidgets('LoginScreen smoke test and UI rendering', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AuthProvider()),
          ChangeNotifierProvider(create: (_) => StudentProvider()),
          ChangeNotifierProvider(create: (_) => StaffProvider()),
          ChangeNotifierProvider(create: (_) => AttendanceProvider()),
          ChangeNotifierProvider(create: (_) => ConfigProvider()),
        ],
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          home: const LoginScreen(),
        ),
      ),
    );

    // Verify institutional title and login buttons
    expect(find.text('Hostel Attendance Portal'), findsOneWidget);
    expect(find.text('Student Login'), findsOneWidget);
    expect(find.text('Staff / Admin'), findsOneWidget);
    expect(find.text('Sign In'), findsOneWidget);
  });
}
