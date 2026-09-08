from datetime import date
#from .eta import compute_scheduled_arrivals
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

#from .models import GPSPing, Passenger, Trip, TripPassenger, TripStop
#from .permissions import IsDriver, IsParent
from .serializers import (
    GPSPingInputSerializer, PassengerSerializer, TripSerializer,
)

from django.db.models import Count, Q
from .models import GPSPing, Organization, Passenger, Route, Trip, TripPassenger, TripStop, Vehicle
from .permissions import IsDriver, IsOrgAdmin, IsParent
from .eta import compute_scheduled_arrivals, estimate_eta_minutes


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

        # Lock in the "promised" arrival times for this trip, based on
        # the route's stop sequence at baseline speed -- these never
        # change again, even as live conditions do.
        stops = [ts.stop for ts in trip.trip_stops.select_related("stop").order_by("stop__sequence")]
        scheduled = compute_scheduled_arrivals(stops, trip.started_at)
        for trip_stop in trip.trip_stops.all():
            trip_stop.scheduled_arrival_at = scheduled.get(trip_stop.stop_id)
            trip_stop.save(update_fields=["scheduled_arrival_at"])

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




    
# ---------------------------------------------------------------------
# Traffic / alternate-route scenario
# ---------------------------------------------------------------------

class DetectTrafficView(APIView):
    """
    Simulates the platform detecting heavy traffic on the current
    route (in production this would come from a real traffic API).
    Immediately affects ETA calculations via eta.py.
    """

    permission_classes = [IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        trip.traffic_detected = True
        trip.alt_route_active = False
        trip.save()
        return Response(TripSerializer(trip).data)


class UseAlternateRouteView(APIView):
    """Driver accepts the suggested alternate route -- clears the
    traffic flag and applies the faster-route ETA multiplier instead."""

    permission_classes = [IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        trip.alt_route_active = True
        trip.save()
        return Response(TripSerializer(trip).data)


class ClearTrafficView(APIView):
    """Resets both flags -- lets the demo be replayed without restarting the trip."""

    permission_classes = [IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        trip.traffic_detected = False
        trip.alt_route_active = False
        trip.save()
        return Response(TripSerializer(trip).data)



# ---------------------------------------------------------------------
# Organization dashboard -- Phase 1 (Dashboard metrics + Live Fleet)
# ---------------------------------------------------------------------

def _org_for_admin(user):
    """
    Scopes an org_admin to their assigned organization. Falls back to
    the first Organization in the database for a superuser created
    without one attached (e.g. the initial ensure_superuser account) --
    fine for a single-org pilot; revisit once there's more than one
    real organization on the platform.
    """
    if user.organization:
        return user.organization
    return Organization.objects.first()


class OrgDashboardMetricsView(APIView):
    """
    Answers "what is happening across my entire transportation
    operation right now" in one call. Every number here is a real
    query against the same data Parent/Driver already read and write --
    nothing here is mocked or hardcoded.
    """

    permission_classes = [IsOrgAdmin]

    def get(self, request):
        org = _org_for_admin(request.user)
        if org is None:
            return Response({"detail": "No organization found."}, status=404)

        today = date.today()
        User = request.user.__class__

        todays_trips = Trip.objects.filter(route__organization=org, date=today)
        active_driver_ids = todays_trips.exclude(driver=None).values_list("driver_id", flat=True).distinct()

        data = {
            "organization": {"id": str(org.id), "name": org.name, "org_type": org.org_type},
            "total_vehicles": Vehicle.objects.filter(organization=org).count(),
            "active_vehicles": Vehicle.objects.filter(organization=org, is_active=True).count(),
            "total_drivers": User.objects.filter(organization=org, role="driver").count(),
            "active_drivers": active_driver_ids.count(),
            "total_passengers": Passenger.objects.filter(organization=org, active=True).count(),
            "total_parents": User.objects.filter(role="parent", wards__organization=org).distinct().count(),
            "total_employees": User.objects.filter(organization=org, role__in=["driver", "org_admin"]).count(),
            "active_routes": Route.objects.filter(organization=org, is_active=True).count(),
            "todays_trips": todays_trips.count(),
            # Placeholder proxy until the full Safety & Alerts Center
            # (Phase 4) exists -- counts trips currently flagged with
            # traffic, which is real data, just not yet a full alerts model.
            "active_alerts": todays_trips.filter(traffic_detected=True).count(),
        }
        return Response(data)


class OrgLiveFleetView(APIView):
    """
    One row per trip running today for this organization -- vehicle,
    driver, route, live position, next-stop ETA/delay, and passenger
    counts. This is the same Trip/TripStop/TripPassenger data the
    Driver and Parent apps already read; nothing new is computed here
    except aggregating it into one list for the org view.
    """

    permission_classes = [IsOrgAdmin]

    def get(self, request):
        org = _org_for_admin(request.user)
        if org is None:
            return Response({"detail": "No organization found."}, status=404)

        trips = Trip.objects.filter(route__organization=org, date=date.today()).select_related(
            "route", "vehicle", "driver"
        ).prefetch_related("trip_stops__stop", "trip_passengers")

        results = []
        for trip in trips:
            next_stop = trip.trip_stops.exclude(status__in=["arrived", "skipped"]).order_by("stop__sequence").first()
            eta_minutes = None
            if next_stop and trip.last_lat is not None:
                eta_minutes = estimate_eta_minutes(
                    trip.last_lat, trip.last_lng, next_stop.stop.latitude, next_stop.stop.longitude,
                    traffic_detected=trip.traffic_detected, alt_route_active=trip.alt_route_active,
                )

            total_passengers = trip.trip_passengers.count()
            boarded = trip.trip_passengers.filter(status__in=["boarded", "dropped_off"]).count()
            absent = trip.trip_passengers.filter(status__in=["absent", "no_show"]).count()

            results.append({
                "trip_id": str(trip.id),
                "vehicle_label": trip.vehicle.label if trip.vehicle else None,
                "driver_name": trip.driver.get_full_name() if trip.driver else None,
                "route_name": trip.route.name,
                "route_type": trip.route.route_type,
                "status": trip.status,
                "is_replacement_driver": trip.is_replacement_driver,
                "last_lat": trip.last_lat,
                "last_lng": trip.last_lng,
                "last_ping_at": trip.last_ping_at,
                "traffic_detected": trip.traffic_detected,
                "alt_route_active": trip.alt_route_active,
                "next_stop_name": next_stop.stop.name if next_stop else None,
                "eta_minutes": eta_minutes,
                "passengers_total": total_passengers,
                "passengers_boarded": boarded,
                "passengers_absent": absent,
            })

        return Response(results)