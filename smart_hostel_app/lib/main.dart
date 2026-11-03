import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/theme/app_theme.dart';
import 'models/user_model.dart';
import 'providers/auth_provider.dart';
import 'providers/student_provider.dart';
import 'providers/staff_provider.dart';
import 'providers/attendance_provider.dart';
import 'providers/config_provider.dart';
import 'services/notification_service.dart';

import 'features/authentication/splash_screen.dart';
import 'features/authentication/login_screen.dart';
import 'features/student/student_dashboard_screen.dart';
import 'features/student/attendance_history_screen.dart';
import 'features/student/attendance_analytics_screen.dart';
import 'features/student/student_profile_screen.dart';
import 'features/attendance/location_verification_screen.dart';
import 'features/attendance/facial_recognition_screen.dart';
import 'features/attendance/attendance_success_screen.dart';
import 'features/staff/staff_dashboard_screen.dart';
import 'features/staff/student_management_screen.dart';
import 'features/staff/add_student_screen.dart';
import 'features/staff/student_detail_screen.dart';
import 'features/staff/absent_students_screen.dart';
import 'features/staff/daily_monitoring_screen.dart';
import 'features/reports/reports_screen.dart';
import 'features/staff/admin_settings_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await NotificationService.init();

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => StudentProvider()),
        ChangeNotifierProvider(create: (_) => StaffProvider()),
        ChangeNotifierProvider(create: (_) => AttendanceProvider()),
        ChangeNotifierProvider(create: (_) => ConfigProvider()),
      ],
      child: const SmartHostelAttendanceApp(),
    ),
  );
}

class SmartHostelAttendanceApp extends StatelessWidget {
  const SmartHostelAttendanceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart Hostel Attendance System',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      initialRoute: '/',
      onGenerateRoute: (settings) {
        switch (settings.name) {
          case '/':
            return MaterialPageRoute(builder: (_) => const SplashScreen());
          case '/login':
            return MaterialPageRoute(builder: (_) => const LoginScreen());
          case '/student-dashboard':
            return MaterialPageRoute(builder: (_) => const StudentDashboardScreen());
          case '/location-verification':
            return MaterialPageRoute(builder: (_) => const LocationVerificationScreen());
          case '/facial-recognition':
            return MaterialPageRoute(builder: (_) => const FacialRecognitionScreen());
          case '/attendance-success':
            return MaterialPageRoute(builder: (_) => const AttendanceSuccessScreen());
          case '/attendance-history':
            return MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen());
          case '/attendance-analytics':
            return MaterialPageRoute(builder: (_) => const AttendanceAnalyticsScreen());
          case '/student-profile':
            return MaterialPageRoute(builder: (_) => const StudentProfileScreen());
          case '/staff-dashboard':
            return MaterialPageRoute(builder: (_) => const StaffDashboardScreen());
          case '/student-management':
            return MaterialPageRoute(builder: (_) => const StudentManagementScreen());
          case '/add-student':
            return MaterialPageRoute(builder: (_) => const AddStudentScreen());
          case '/student-detail':
            final student = settings.arguments as UserModel;
            return MaterialPageRoute(builder: (_) => StudentDetailScreen(student: student));
          case '/absent-students':
            return MaterialPageRoute(builder: (_) => const AbsentStudentsScreen());
          case '/daily-monitoring':
            return MaterialPageRoute(builder: (_) => const DailyMonitoringScreen());
          case '/reports':
            return MaterialPageRoute(builder: (_) => const ReportsScreen());
          case '/admin-settings':
            return MaterialPageRoute(builder: (_) => const AdminSettingsScreen());
          default:
            return MaterialPageRoute(builder: (_) => const SplashScreen());
        }
      },
    );
  }
}
