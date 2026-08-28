"""
Simple haversine-based ETA estimate for V1.

This is intentionally NOT a real routing engine -- it estimates
straight-line distance from the vehicle's last known position to a
stop, divided by an assumed average speed. Good enough to demo and to
validate the product loop; swap for a real routing/traffic API
(Google Routes, etc.) once there's budget and real usage data to
justify it (see the brief's AI/ML + routing sections).
"""

import math

AVERAGE_SPEED_KMH = 22  # rough urban/school-route average


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    lat1, lng1, lat2, lng2 = map(float, (lat1, lng1, lat2, lng2))
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_eta_minutes(from_lat, from_lng, to_lat, to_lng) -> int:
    if from_lat is None or from_lng is None:
        return None
    distance_km = haversine_km(from_lat, from_lng, to_lat, to_lng)
    hours = distance_km / AVERAGE_SPEED_KMH
    return max(1, round(hours * 60))
