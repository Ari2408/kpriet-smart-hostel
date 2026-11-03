import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

class CampusRadarWidget extends StatefulWidget {
  final bool insideGeofence;
  final double distanceMeters;
  final double radiusMeters;
  final String campusName;

  const CampusRadarWidget({
    super.key,
    required this.insideGeofence,
    required this.distanceMeters,
    required this.radiusMeters,
    required this.campusName,
  });

  @override
  State<CampusRadarWidget> createState() => _CampusRadarWidgetState();
}

class _CampusRadarWidgetState extends State<CampusRadarWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = widget.insideGeofence
        ? AppColors.presentGreen
        : AppColors.absentRed;

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.dividerColor),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          SizedBox(
            width: 180,
            height: 180,
            child: Stack(
              alignment: Alignment.center,
              children: [
                // Animated pulse wave
                AnimatedBuilder(
                  animation: _pulseController,
                  builder: (context, child) {
                    return Container(
                      width: 80 + (_pulseController.value * 90),
                      height: 80 + (_pulseController.value * 90),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: statusColor.withOpacity(1.0 - _pulseController.value),
                          width: 2,
                        ),
                      ),
                    );
                  },
                ),
                // Outer Campus Geofence Boundary ring
                Container(
                  width: 140,
                  height: 140,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: AppColors.primaryNavy.withOpacity(0.3),
                      width: 2,
                      style: BorderStyle.solid,
                    ),
                    color: AppColors.primaryNavy.withOpacity(0.04),
                  ),
                ),
                // Center pin
                Container(
                  width: 54,
                  height: 54,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: statusColor,
                    boxShadow: [
                      BoxShadow(
                        color: statusColor.withOpacity(0.4),
                        blurRadius: 12,
                        spreadRadius: 2,
                      ),
                    ],
                  ),
                  child: Icon(
                    widget.insideGeofence
                        ? Icons.location_on_rounded
                        : Icons.location_off_rounded,
                    color: Colors.white,
                    size: 30,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Text(
            widget.insideGeofence ? "INSIDE CAMPUS PERIMETER" : "OUTSIDE CAMPUS BOUNDARY",
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: statusColor,
              letterSpacing: 0.6,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            widget.distanceMeters >= 0
                ? "${widget.distanceMeters.toStringAsFixed(1)} m from campus center (Radius: ${widget.radiusMeters.toStringAsFixed(0)} m)"
                : "Acquiring GPS fix...",
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
              fontWeight: FontWeight.w500,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
