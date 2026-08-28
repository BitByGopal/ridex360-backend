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

    class Meta:
        model = TripStop
        fields = ["id", "stop", "status", "arrived_at", "eta_minutes"]

    def get_eta_minutes(self, obj):
        trip = obj.trip
        if trip.last_lat is None:
            return None
        return estimate_eta_minutes(trip.last_lat, trip.last_lng, obj.stop.latitude, obj.stop.longitude)


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
