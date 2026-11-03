import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

class StatusBadge extends StatelessWidget {
  final String status;
  final double fontSize;
  final EdgeInsets padding;

  const StatusBadge({
    super.key,
    required this.status,
    this.fontSize = 12,
    this.padding = const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
  });

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color fg;
    IconData icon;
    String label = status.toUpperCase();

    switch (label) {
      case "PRESENT":
        bg = AppColors.presentGreenLight;
        fg = AppColors.presentGreen;
        icon = Icons.check_circle_rounded;
        break;
      case "ABSENT":
        bg = AppColors.absentRedLight;
        fg = AppColors.absentRed;
        icon = Icons.cancel_rounded;
        break;
      case "PENDING":
      default:
        bg = AppColors.pendingOrangeLight;
        fg = AppColors.pendingOrange;
        icon = Icons.access_time_filled_rounded;
        label = "PENDING";
        break;
    }

    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: fg.withOpacity(0.3), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: fontSize + 2, color: fg),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: fg,
              fontSize: fontSize,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.4,
            ),
          ),
        ],
      ),
    );
  }
}
