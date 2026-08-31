"""
ETA calculation for V1 -- haversine-distance-based, not a real routing
engine. Good enough to demo and validate the product loop; swap for a
real routing/traffic API (Google Routes, etc.) once there's budget and
real usage data to justify it.

Two distinct numbers, per the product spec:

- SCHEDULED arrival: computed once, when the driver starts the trip,
  using cumulative distance along the route's stop sequence at the
  baseline average speed. This never changes during the trip -- it's
  "what we told the passenger to expect."

- LIVE arrival: recalculated on every request from the vehicle's last
  known GPS position, factoring in traffic_detected/alt_route_active.
  This is "what's actually going to happen right now."

The difference between the two is the delay shown to passengers.
Both are served as absolute datetimes from the backend (not just
relative minutes), so Parent, Passenger, Driver, and Organization
interfaces all read the same numbers instead of each computing their
own.
"""

import math
from datetime import timedelta

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


def compute_scheduled_arrivals(stops, start_time):
    """
    stops: an ordered iterable of Stop objects (by .sequence), each
    with .id, .latitude, .longitude.
    start_time: the datetime the trip actually started.

    Returns {stop_id: scheduled_arrival_datetime}, using cumulative
    haversine distance along the stop sequence at the baseline speed
    (no traffic factored in -- this is the "promise", not the live
    prediction).
    """
    arrivals = {}
    cumulative_km = 0.0
    prev = None
    for stop in stops:
        if prev is not None:
            cumulative_km += haversine_km(prev.latitude, prev.longitude, stop.latitude, stop.longitude)
        hours = cumulative_km / AVERAGE_SPEED_KMH
        arrivals[stop.id] = start_time + timedelta(hours=hours)
        prev = stop
    return arrivals