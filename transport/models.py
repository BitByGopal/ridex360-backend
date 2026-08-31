import uuid
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Organization layer
# ---------------------------------------------------------------------------

class Organization(models.Model):
    """
    A tenant. Could be a school group, a company, a hospital network.
    ORG_TYPE decides the terminology the mobile apps display (e.g.
    'Student'/'Parent' for a school vs 'Employee' for a company) without
    changing any of the underlying workflow logic.
    """

    class OrgType(models.TextChoices):
        SCHOOL = "school", "School"
        COLLEGE = "college", "College"
        COMPANY = "company", "Company"
        HOSPITAL = "hospital", "Hospital"
        FACTORY = "factory", "Factory"
        HOTEL = "hotel", "Hotel"
        INDUSTRIAL = "industrial", "Industrial Campus"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=20, choices=OrgType.choices)
    city = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Branch(models.Model):
    """
    A physical site under an Organization. Meridian Schools, for
    example, is one Organization with three Branches. Transport is
    scoped to a Branch: routes, vehicles and drivers all belong to one
    branch, even if branches share a parent organization.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Branches"

    def __str__(self):
        return f"{self.organization.name} -- {self.name}"


# ---------------------------------------------------------------------------
# People being transported
# ---------------------------------------------------------------------------

class Passenger(models.Model):
    """
    The person being transported -- a Student at a school, an Employee
    at a company, Staff at a hospital, etc. Named generically on
    purpose so the same table/workflow serves every organization type;
    the display label comes from Organization.org_type in the API layer.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="passengers")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="passengers")
    full_name = models.CharField(max_length=200)
    # Free-form org-specific detail: grade/section for a school,
    # department/shift for a company, etc. Avoids a schema migration
    # every time a new organization type needs a different field.
    detail = models.CharField(max_length=200, blank=True, help_text="e.g. 'Grade 4B' or 'Engineering, Shift A'")
    pickup_stop = models.ForeignKey(
        "Stop", null=True, blank=True, on_delete=models.SET_NULL, related_name="pickup_passengers"
    )
    guardians = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="wards",
        limit_choices_to={"role": "parent"},
        help_text="Parent/guardian user accounts authorized to manage this passenger's transport.",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


# ---------------------------------------------------------------------------
# Fleet
# ---------------------------------------------------------------------------

class Vehicle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="vehicles")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="vehicles")
    label = models.CharField(max_length=50, help_text="e.g. 'Bus 12'")
    registration_number = models.CharField(max_length=30, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.label


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class Route(models.Model):
    class RouteType(models.TextChoices):
        MORNING = "morning", "Morning"
        EVENING = "evening", "Evening"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="routes")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="routes")
    name = models.CharField(max_length=100, help_text="e.g. 'Route A -- Main Road Line'")
    route_type = models.CharField(max_length=10, choices=RouteType.choices)
    default_vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    default_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="default_routes", limit_choices_to={"role": "driver"},
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_route_type_display()})"


class Stop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    sequence = models.PositiveIntegerField(help_text="Order along the route, starting at 1")
    name = models.CharField(max_length=150)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        ordering = ["route", "sequence"]
        unique_together = ("route", "sequence")

    def __str__(self):
        return f"{self.route.name} -- Stop {self.sequence}: {self.name}"


# ---------------------------------------------------------------------------
# Trips -- one Route generates one Trip per day it runs
# ---------------------------------------------------------------------------

class Trip(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="trips")
    date = models.DateField(default=date.today)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)

    # The vehicle/driver actually running this trip -- may differ from
    # the route's defaults when a replacement driver takes over.
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="trips")
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="trips", limit_choices_to={"role": "driver"},
    )
    is_replacement_driver = models.BooleanField(default=False)
        # Traffic / alternate-route scenario. traffic_detected simulates a
    # slowdown on the current route; alt_route_active means the driver
    # has switched to a faster alternative. Both feed into the ETA
    # calculation in eta.py rather than being purely cosmetic flags.
    traffic_detected = models.BooleanField(default=False)
    alt_route_active = models.BooleanField(default=False)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Live position -- updated on every GPS ping. Kept denormalized on
    # the Trip itself (rather than always querying GPSPing history) so
    # a parent's "where's the bus" screen is a single cheap read.
    last_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_ping_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("route", "date")

    def __str__(self):
        return f"{self.route.name} -- {self.date}"


class TripStop(models.Model):
    """
    Per-trip copy of a route's stops. Exists separately from Stop
    because a given day's trip might skip a stop entirely (every
    passenger assigned to it marked absent) -- that's tracked here,
    not on the reusable Stop template.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROACHING = "approaching", "Approaching"
        ARRIVED = "arrived", "Arrived"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="trip_stops")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    arrived_at = models.DateTimeField(null=True, blank=True)
    # Set once, when the trip starts (see StartTripView) -- the
    # "promised" arrival time, independent of live traffic conditions.
    # Compared against the live ETA to compute and display delay.
    scheduled_arrival_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["stop__sequence"]
        unique_together = ("trip", "stop")


class TripPassenger(models.Model):
    """
    Per-trip status for a single passenger. This is where the absence
    workflow lives: marking a passenger absent here (and checking
    whether their stop has any other active passenger left) is what
    triggers a TripStop being marked SKIPPED.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ABSENT = "absent", "Absent"
        WAITING = "waiting", "Waiting"
        BOARDED = "boarded", "Boarded"
        DROPPED_OFF = "dropped_off", "Dropped off"
        NO_SHOW = "no_show", "No-show"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="trip_passengers")
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, related_name="trip_records")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)

    marked_absent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    marked_absent_at = models.DateTimeField(null=True, blank=True)
    boarded_at = models.DateTimeField(null=True, blank=True)
    dropped_off_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("trip", "passenger")

    def __str__(self):
        return f"{self.passenger.full_name} -- {self.trip} ({self.status})"


class GPSPing(models.Model):
    """
    Append-only GPS history for a trip. Trip.last_lat/last_lng is the
    fast-read cache; this table is the full trail (useful later for
    route-deviation detection, playback, and analytics).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="gps_pings")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at"]
