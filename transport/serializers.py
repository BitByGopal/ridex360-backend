from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .eta import estimate_eta_minutes
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
        """The live, continuously-recalculated prediction, as an
        absolute time -- distinct from scheduled_arrival_at, which is
        fixed once the trip starts. Both are served so every client
        (Parent/Passenger/Driver/Organization) reads the same numbers
        instead of computing their own from raw minutes.

        Explicitly localized to match how DRF renders scheduled_arrival_at
        (a direct model field) -- without this, a SerializerMethodField
        returning a raw datetime serializes in UTC while the model field
        serializes in the active timezone, which is the same instant but
        looks inconsistent in the JSON."""
        eta_minutes = self.get_eta_minutes(obj)
        if eta_minutes is None:
            return None
        return timezone.localtime(timezone.now() + timedelta(minutes=eta_minutes))

    def get_delay_minutes(self, obj):
        """Positive = running late vs. the original schedule.
        Negative = running early (e.g. alternate route beat the plan)."""
        live = self.get_live_arrival_at(obj)
        if live is None or obj.scheduled_arrival_at is None:
            return None
        return round((live - obj.scheduled_arrival_at).total_seconds() / 60)


class TripPassengerSerializer(serializers.ModelSerializer):
    passenger_name = serializers.CharField(source="passenger.full_name", read_only=True)

    class Meta:
        model = TripPassenger
        fields = ["id", "passenger", "passenger_name", "status", "boarded_at", "dropped_off_at"]


class TripSerializer(serializers.ModelSerializer):
    route = RouteSerializer(read_only=True)
    trip_stops = TripStopSerializer(many=True, read_only=True)
    trip_passengers = TripPassengerSerializer(many=True, read_only=True)
    vehicle_label = serializers.CharField(source="vehicle.label", read_only=True)
    driver_name = serializers.CharField(source="driver.get_full_name", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id", "route", "date", "status", "vehicle", "vehicle_label",
            "driver", "driver_name", "is_replacement_driver",
            "started_at", "completed_at",
            "last_lat", "last_lng", "last_ping_at",
            "traffic_detected", "alt_route_active",
            "trip_stops", "trip_passengers",
        ]


class PassengerSerializer(serializers.ModelSerializer):
    organization_type = serializers.CharField(source="organization.org_type", read_only=True)

    class Meta:
        model = Passenger
        fields = ["id", "full_name", "detail", "organization", "organization_type", "branch", "pickup_stop", "active"]


class GPSPingInputSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)