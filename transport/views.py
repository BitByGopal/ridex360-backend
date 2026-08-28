from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GPSPing, Passenger, Trip, TripPassenger, TripStop
from .permissions import IsDriver, IsParent
from .serializers import (
    GPSPingInputSerializer, PassengerSerializer, TripSerializer,
)


class MeView(APIView):
    """Returns the logged-in user's role + basic profile -- the mobile
    app calls this right after login to decide which screens to show."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.get_full_name(),
            "role": user.role,
            "phone": user.phone,
        }
        if user.organization:
            data["organization"] = {
                "id": str(user.organization.id),
                "name": user.organization.name,
                "org_type": user.organization.org_type,
            }
        return Response(data)


# ---------------------------------------------------------------------
# Parent-facing endpoints
# ---------------------------------------------------------------------

class MyChildrenView(APIView):
    """List the passengers this parent is a guardian of."""

    permission_classes = [IsParent]

    def get(self, request):
        passengers = Passenger.objects.filter(guardians=request.user, active=True)
        return Response(PassengerSerializer(passengers, many=True).data)


class ChildTodayTripView(APIView):
    """Today's trip status for one of the parent's children -- the
    core 'where's my bus' screen."""

    permission_classes = [IsParent]

    def get(self, request, passenger_id):
        passenger = get_object_or_404(Passenger, id=passenger_id, guardians=request.user)
        if not passenger.pickup_stop:
            return Response({"detail": "No pickup stop assigned."}, status=404)

        route = passenger.pickup_stop.route
        trip = Trip.objects.filter(route=route, date=date.today()).first()
        if not trip:
            return Response({"detail": "No trip scheduled today."}, status=404)

        return Response(TripSerializer(trip).data)


class MarkAbsentView(APIView):
    """
    The core-loop moment: a parent marks their child absent for
    today's trip. This:
      1. Sets that passenger's TripPassenger status to ABSENT.
      2. Checks whether their pickup stop has any other
         SCHEDULED/WAITING passenger left today.
      3. If not, marks that TripStop as SKIPPED -- which is what makes
         the stop disappear from the driver's active route.
    """

    permission_classes = [IsParent]

    def post(self, request, passenger_id):
        passenger = get_object_or_404(Passenger, id=passenger_id, guardians=request.user)
        if not passenger.pickup_stop:
            return Response({"detail": "No pickup stop assigned."}, status=400)

        route = passenger.pickup_stop.route
        trip = Trip.objects.filter(route=route, date=date.today()).first()
        if not trip:
            return Response({"detail": "No trip scheduled today."}, status=404)

        trip_passenger, _ = TripPassenger.objects.get_or_create(trip=trip, passenger=passenger)
        trip_passenger.status = TripPassenger.Status.ABSENT
        trip_passenger.marked_absent_by = request.user
        trip_passenger.marked_absent_at = timezone.now()
        trip_passenger.save()

        # Recalculate: does this passenger's stop still have anyone active?
        stop = passenger.pickup_stop
        other_active_passengers = TripPassenger.objects.filter(
            trip=trip,
            passenger__pickup_stop=stop,
        ).exclude(status__in=[TripPassenger.Status.ABSENT, TripPassenger.Status.NO_SHOW]).exists()

        trip_stop = TripStop.objects.filter(trip=trip, stop=stop).first()
        if trip_stop and not other_active_passengers:
            trip_stop.status = TripStop.Status.SKIPPED
            trip_stop.save()

        return Response(TripSerializer(trip).data)


# ---------------------------------------------------------------------
# Driver-facing endpoints
# ---------------------------------------------------------------------

class MyTripsTodayView(APIView):
    permission_classes = [IsDriver]

    def get(self, request):
        trips = Trip.objects.filter(driver=request.user, date=date.today())
        return Response(TripSerializer(trips, many=True).data)


class StartTripView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        trip.status = Trip.Status.ACTIVE
        trip.started_at = timezone.now()
        trip.save()
        return Response(TripSerializer(trip).data)


class CompleteTripView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        trip.status = Trip.Status.COMPLETED
        trip.completed_at = timezone.now()
        trip.save()
        return Response(TripSerializer(trip).data)


class GPSPingView(APIView):
    """
    Driver app posts a GPS point on an interval (polling, not
    WebSockets, for V1 -- see the roadmap notes on why). Updates the
    Trip's fast-read cache and appends to the ping history table.
    """

    permission_classes = [IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        serializer = GPSPingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data["latitude"]
        lng = serializer.validated_data["longitude"]

        GPSPing.objects.create(trip=trip, latitude=lat, longitude=lng)
        trip.last_lat = lat
        trip.last_lng = lng
        trip.last_ping_at = timezone.now()
        trip.save()

        return Response(TripSerializer(trip).data)


class StopArrivedView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, trip_id, trip_stop_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        trip_stop = get_object_or_404(TripStop, id=trip_stop_id, trip=trip)
        trip_stop.status = TripStop.Status.ARRIVED
        trip_stop.arrived_at = timezone.now()
        trip_stop.save()
        return Response(TripSerializer(trip).data)


class PassengerBoardedView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, trip_id, trip_passenger_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        tp = get_object_or_404(TripPassenger, id=trip_passenger_id, trip=trip)
        tp.status = TripPassenger.Status.BOARDED
        tp.boarded_at = timezone.now()
        tp.save()
        return Response(TripSerializer(trip).data)


class PassengerDroppedOffView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, trip_id, trip_passenger_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        tp = get_object_or_404(TripPassenger, id=trip_passenger_id, trip=trip)
        tp.status = TripPassenger.Status.DROPPED_OFF
        tp.dropped_off_at = timezone.now()
        tp.save()
        return Response(TripSerializer(trip).data)


class PassengerNoShowView(APIView):
    """Driver-side equivalent of absence -- used when a passenger
    wasn't marked absent in advance but doesn't show up at the stop."""

    permission_classes = [IsDriver]

    def post(self, request, trip_id, trip_passenger_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        tp = get_object_or_404(TripPassenger, id=trip_passenger_id, trip=trip)
        tp.status = TripPassenger.Status.NO_SHOW
        tp.save()
        return Response(TripSerializer(trip).data)
