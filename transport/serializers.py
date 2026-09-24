from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .eta import estimate_eta_minutes, haversine_km
from .models import GPSPing, Passenger, Route, Stop, Trip, TripPassenger, TripStop


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = ["id", "sequence", "name", "latitude", "longitude"]


class RouteSerializer(serializers.ModelSerializer):
    stops = StopSerializer(many=True, read_only=True)

    class Meta:
        model = Route
        fields = ["id", "name", "route_type", "stops"]


class TripStopSerializer(serializers.ModelSerializer):
    stop = StopSerializer(read_only=True)
    eta_minutes = serializers.SerializerMethodField()
    live_arrival_at = serializers.SerializerMethodField()
    delay_minutes = serializers.SerializerMethodField()

    class Meta:
        model = TripStop
        fields = [
            "id", "stop", "status", "arrived_at",
            "eta_minutes", "scheduled_arrival_at", "live_arrival_at", "delay_minutes",
        ]

    def get_eta_minutes(self, obj):
        trip = obj.trip
        if trip.last_lat is None:
            return None
        return estimate_eta_minutes(
            trip.last_lat, trip.last_lng, obj.stop.latitude, obj.stop.longitude,
            traffic_detected=trip.traffic_detected, alt_route_active=trip.alt_route_active,
        )

    def get_live_arrival_at(self, obj):
        eta_minutes = self.get_eta_minutes(obj)
        if eta_minutes is None:
            return None
        return timezone.localtime(timezone.now() + timedelta(minutes=eta_minutes))

    def get_delay_minutes(self, obj):
        live = self.get_live_arrival_at(obj)
        if live is None or obj.scheduled_arrival_at is None:
            return None
        return round((live - obj.scheduled_arrival_at).total_seconds() / 60)


class TripPassengerSerializer(serializers.ModelSerializer):
    passenger_name = serializers.CharField(source="passenger.full_name", read_only=True)
    passenger_detail = serializers.CharField(source="passenger.detail", read_only=True)
    pickup_stop_id = serializers.SerializerMethodField()
    pickup_stop_name = serializers.SerializerMethodField()

    class Meta:
        model = TripPassenger
        fields = [
            "id", "passenger", "passenger_name", "passenger_detail",
            "pickup_stop_id", "pickup_stop_name", "status", "boarded_at", "dropped_off_at",
        ]

    def get_pickup_stop_id(self, obj):
        return str(obj.passenger.pickup_stop_id) if obj.passenger.pickup_stop_id else None

    def get_pickup_stop_name(self, obj):
        return obj.passenger.pickup_stop.name if obj.passenger.pickup_stop else None


class TripSerializer(serializers.ModelSerializer):
    route = RouteSerializer(read_only=True)
    trip_stops = TripStopSerializer(many=True, read_only=True)
    trip_passengers = TripPassengerSerializer(many=True, read_only=True)
    vehicle_label = serializers.CharField(source="vehicle.label", read_only=True)
    driver_name = serializers.CharField(source="driver.get_full_name", read_only=True)
    driver_phone = serializers.CharField(source="driver.phone", read_only=True)
    current_speed_kmh = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "id", "route", "date", "status", "vehicle", "vehicle_label",
            "driver", "driver_name", "driver_phone", "is_replacement_driver",
            "started_at", "completed_at",
            "last_lat", "last_lng", "last_ping_at", "current_speed_kmh",
            "traffic_detected", "alt_route_active",
            "trip_stops", "trip_passengers",
        ]

    def get_current_speed_kmh(self, obj):
        """
        Computed from the two most recent real GPS pings -- not
        simulated. Returns None until at least two pings exist (i.e.
        right when a trip starts), which is the honest state rather
        than showing a fake 0 km/h.
        """
        pings = list(obj.gps_pings.order_by("-recorded_at")[:2])
        if len(pings) < 2:
            return None
        newer, older = pings[0], pings[1]
        seconds = (newer.recorded_at - older.recorded_at).total_seconds()
        if seconds <= 0:
            return None
        distance_km = haversine_km(older.latitude, older.longitude, newer.latitude, newer.longitude)
        speed = distance_km / (seconds / 3600)
        return round(speed, 1)


class PassengerSerializer(serializers.ModelSerializer):
    organization_type = serializers.CharField(source="organization.org_type", read_only=True)

    class Meta:
        model = Passenger
        fields = ["id", "full_name", "detail", "organization", "organization_type", "branch", "pickup_stop", "active"]


class GPSPingInputSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)