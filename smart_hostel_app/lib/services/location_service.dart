import 'package:geolocator/geolocator.dart';
import '../core/utils/geo_utils.dart';

class LocationResult {
  final bool success;
  final double latitude;
  final double longitude;
  final bool isMocked;
  final double? distanceMeters;
  final String? errorMessage;

  LocationResult({
    required this.success,
    this.latitude = 0.0,
    this.longitude = 0.0,
    this.isMocked = false,
    this.distanceMeters,
    this.errorMessage,
  });
}

class LocationService {
  static Future<LocationResult> getCurrentLocation({
    double? targetCampusLat,
    double? targetCampusLon,
  }) async {
    bool serviceEnabled;
    LocationPermission permission;

    // Test if location services are enabled on the device.
    serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return LocationResult(
        success: false,
        errorMessage: "Location services (GPS) are disabled on your device. Please turn on GPS to register attendance.",
      );
    }

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        return LocationResult(
          success: false,
          errorMessage: "Location permissions are denied. Geofence verification requires GPS access.",
        );
      }
    }

    if (permission == LocationPermission.deniedForever) {
      return LocationResult(
        success: false,
        errorMessage: "Location permissions are permanently denied. Please enable them in App Settings.",
      );
    }

    try {
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 15),
      );

      double? dist;
      if (targetCampusLat != null && targetCampusLon != null) {
        dist = GeoUtils.calculateDistanceMeters(
          position.latitude,
          position.longitude,
          targetCampusLat,
          targetCampusLon,
        );
      }

      return LocationResult(
        success: true,
        latitude: position.latitude,
        longitude: position.longitude,
        isMocked: position.isMocked,
        distanceMeters: dist,
      );
    } catch (e) {
      return LocationResult(
        success: false,
        errorMessage: "Failed to acquire GPS fix: ${e.toString()}",
      );
    }
  }
}
