"""
Simple haversine-based ETA estimate for V1.

This is intentionally NOT a real routing engine -- it estimates
straight-line distance from the vehicle's last known position to a
stop, divided by an assumed average speed. Good enough to demo and to
validate the product loop; swap for a real routing/traffic API
(Google Routes, etc.) once there's budget and real usage data to
justify it (see the brief's AI/ML + routing sections).

Traffic/alternate-route scenario: rather than a purely cosmetic toggle,
traffic_detected and alt_route_active actually adjust the effective
speed used in the ETA calculation, so the numbers shown in the app
change consistently with the scenario the driver has triggered.
"""

import math

AVERAGE_SPEED_KMH = 22  # rough urban/school-route average
TRAFFIC_SPEED_MULTIPLIER = 0.55   # current route, heavy traffic
ALT_ROUTE_SPEED_MULTIPLIER = 1.45  # alternate route, lighter traffic


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    lat1, lng1, lat2, lng2 = map(float, (lat1, lng1, lat2, lng2))
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def effective_speed_kmh(traffic_detected: bool, alt_route_active: bool) -> float:
    if alt_route_active:
        return AVERAGE_SPEED_KMH * ALT_ROUTE_SPEED_MULTIPLIER
    if traffic_detected:
        return AVERAGE_SPEED_KMH * TRAFFIC_SPEED_MULTIPLIER
    return AVERAGE_SPEED_KMH


def estimate_eta_minutes(from_lat, from_lng, to_lat, to_lng, traffic_detected=False, alt_route_active=False) -> int:
    if from_lat is None or from_lng is None:
        return None
    distance_km = haversine_km(from_lat, from_lng, to_lat, to_lng)
    speed = effective_speed_kmh(traffic_detected, alt_route_active)
    hours = distance_km / speed
    return max(1, round(hours * 60))