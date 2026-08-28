from django.contrib import admin

from .models import (
    Branch, GPSPing, Organization, Passenger, Route, Stop, Trip,
    TripPassenger, TripStop, Vehicle,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "org_type", "city", "created_at")
    list_filter = ("org_type",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "address")
    list_filter = ("organization",)


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "organization", "branch", "detail", "pickup_stop", "active")
    list_filter = ("organization", "branch", "active")
    filter_horizontal = ("guardians",)
    search_fields = ("full_name",)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("label", "organization", "branch", "registration_number", "capacity", "is_active")
    list_filter = ("organization", "branch", "is_active")


class StopInline(admin.TabularInline):
    model = Stop
    extra = 1


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "route_type", "default_vehicle", "default_driver", "is_active")
    list_filter = ("branch", "route_type", "is_active")
    inlines = [StopInline]


class TripStopInline(admin.TabularInline):
    model = TripStop
    extra = 0
    readonly_fields = ("stop",)


class TripPassengerInline(admin.TabularInline):
    model = TripPassenger
    extra = 0
    readonly_fields = ("passenger",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("route", "date", "status", "driver", "vehicle", "is_replacement_driver", "last_ping_at")
    list_filter = ("status", "date", "route__branch")
    inlines = [TripStopInline, TripPassengerInline]


@admin.register(GPSPing)
class GPSPingAdmin(admin.ModelAdmin):
    list_display = ("trip", "latitude", "longitude", "recorded_at")
    list_filter = ("trip",)
