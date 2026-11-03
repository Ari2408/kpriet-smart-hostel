import 'dart:math';

class GeoUtils {
  static const double earthRadiusMeters = 6371000.0;

  static double calculateDistanceMeters(
    double lat1, double lon1,
    double lat2, double lon2
  ) {
    final double phi1 = lat1 * pi / 180.0;
    final double phi2 = lat2 * pi / 180.0;
    final double deltaPhi = (lat2 - lat1) * pi / 180.0;
    final double deltaLambda = (lon2 - lon1) * pi / 180.0;

    final double a = sin(deltaPhi / 2.0) * sin(deltaPhi / 2.0) +
        cos(phi1) * cos(phi2) * sin(deltaLambda / 2.0) * sin(deltaLambda / 2.0);

    final double clampedA = a.clamp(0.0, 1.0);
    final double c = 2.0 * atan2(sqrt(clampedA), sqrt(1.0 - clampedA));

    return earthRadiusMeters * c;
  }

  static String formatDistance(double meters) {
    if (meters < 0) return "Unknown";
    if (meters < 1000) {
      return "${meters.toStringAsFixed(1)} m";
    } else {
      return "${(meters / 1000).toStringAsFixed(2)} km";
    }
  }
}
