import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

class FaceGuideOverlay extends StatefulWidget {
  final String challengePrompt;
  final bool isFaceAligned;
  final bool isProcessing;

  const FaceGuideOverlay({
    super.key,
    required this.challengePrompt,
    this.isFaceAligned = true,
    this.isProcessing = false,
  });

  @override
  State<FaceGuideOverlay> createState() => _FaceGuideOverlayState();
}

class _FaceGuideOverlayState extends State<FaceGuideOverlay>
    with SingleTickerProviderStateMixin {
  late AnimationController _scanController;

  @override
  void initState() {
    super.initState();
    _scanController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _scanController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final borderColor = widget.isFaceAligned
        ? AppColors.presentGreen
        : AppColors.accentBlue;

    return Stack(
      children: [
        // Darkened background with oval cutout
        Center(
          child: Container(
            width: 260,
            height: 340,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(160),
              border: Border.all(
                color: borderColor,
                width: 3.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: borderColor.withOpacity(0.35),
                  blurRadius: 18,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: widget.isProcessing
                ? AnimatedBuilder(
                    animation: _scanController,
                    builder: (context, child) {
                      return Align(
                        alignment: Alignment(0, (_scanController.value * 2) - 1),
                        child: Container(
                          height: 3,
                          color: AppColors.presentGreen,
                        ),
                      );
                    },
                  )
                : null,
          ),
        ),

        // Challenge banner on bottom
        Positioned(
          bottom: 40,
          left: 20,
          right: 20,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
            decoration: BoxDecoration(
              color: Colors.black.withOpacity(0.75),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white24),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: const BoxDecoration(
                    color: AppColors.primaryNavy,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.face_retouching_natural_rounded,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        "LIVENESS CHALLENGE",
                        style: TextStyle(
                          color: AppColors.pendingOrange,
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.8,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        widget.challengePrompt,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
