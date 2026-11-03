import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class NotificationService {
  static final FlutterLocalNotificationsPlugin _notificationsPlugin =
      FlutterLocalNotificationsPlugin();

  static Future<void> init() async {
    const AndroidInitializationSettings initializationSettingsAndroid =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const InitializationSettings initializationSettings =
        InitializationSettings(android: initializationSettingsAndroid);

    try {
      await _notificationsPlugin.initialize(initializationSettings);
    } catch (_) {
      // Fallback if launcher icon is missing during test runner
    }
  }

  static Future<void> showNotification({
    required int id,
    required String title,
    required String body,
  }) async {
    const AndroidNotificationDetails androidDetails = AndroidNotificationDetails(
      'hostel_attendance_channel',
      'Hostel Attendance Notifications',
      channelDescription: 'Daily attendance alerts and reminders for KPRIET hostel',
      importance: Importance.max,
      priority: Priority.high,
      showWhen: true,
    );

    const NotificationDetails notificationDetails =
        NotificationDetails(android: androidDetails);

    try {
      await _notificationsPlugin.show(
        id,
        title,
        body,
        notificationDetails,
      );
    } catch (_) {}
  }

  static Future<void> notifyAttendanceSuccess(String timeStr) async {
    await showNotification(
      id: 101,
      title: "Attendance Registered ✅",
      body: "Your attendance was successfully verified at $timeStr.",
    );
  }

  static Future<void> notifyWindowReminder() async {
    await showNotification(
      id: 102,
      title: "Hostel Attendance Window Open ⏰",
      body: "Attendance is open from 7:00 PM to 8:00 PM. Please verify your face and GPS.",
    );
  }

  static Future<void> notifyWindowClosing() async {
    await showNotification(
      id: 103,
      title: "Attendance Window Closing Soon ⚠️",
      body: "Only 15 minutes left before 8:00 PM cutoff. Please mark your attendance now.",
    );
  }

  static Future<void> notifyVerificationFailure(String reason) async {
    await showNotification(
      id: 104,
      title: "Attendance Verification Failed ❌",
      body: reason,
    );
  }
}
