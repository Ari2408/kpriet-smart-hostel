import math
from typing import Tuple, Dict, Any

EARTH_RADIUS_METERS = 6371000.0 # Earth's mean radius in meters

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points
    on the Earth using the Haversine formula.
    Returns distance in meters.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    
    # Clamp 'a' to [0, 1] to avoid math domain errors due to floating-point imprecision
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = EARTH_RADIUS_METERS * c
    return round(distance, 2)

def validate_geofence(
    student_lat: float,
    student_lon: float,
    campus_lat: float,
    campus_lon: float,
    allowed_radius_meters: float,
    is_mock: bool = False
) -> Dict[str, Any]:
    """
    Verify whether the student's coordinates fall within the allowed campus perimeter.
    Detects mock location flags as well as impossible teleportation / out-of-bounds coordinates.
    """
    # 1. Coordinate range sanity check
    if not (-90.0 <= student_lat <= 90.0) or not (-180.0 <= student_lon <= 180.0):
        return {
            "valid": False,
            "inside": False,
            "distance": -1.0,
            "reason": "Invalid GPS coordinates supplied."
        }

    # 2. Check for mock locations
    if is_mock:
        return {
            "valid": False,
            "inside": False,
            "distance": -1.0,
            "reason": "Mock location (Fake GPS) detected. Attendance rejected."
        }

    # 3. Distance computation
    distance = haversine_distance(student_lat, student_lon, campus_lat, campus_lon)
    inside = distance <= allowed_radius_meters

    return {
        "valid": True,
        "inside": inside,
        "distance": distance,
        "radius": allowed_radius_meters,
        "reason": "Within campus geofence boundary." if inside else f"Outside campus geofence. Distance: {distance}m, allowed: {allowed_radius_meters}m"
    }
