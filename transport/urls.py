from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MeView.as_view(), name="me"),

    # Parent
    path("parent/children/", views.MyChildrenView.as_view(), name="my-children"),
    path("parent/children/<uuid:passenger_id>/today/", views.ChildTodayTripView.as_view(), name="child-today-trip"),
    path("parent/children/<uuid:passenger_id>/mark-absent/", views.MarkAbsentView.as_view(), name="mark-absent"),

    # Driver
    path("driver/trips/today/", views.MyTripsTodayView.as_view(), name="driver-trips-today"),
    path("driver/trips/<uuid:trip_id>/start/", views.StartTripView.as_view(), name="trip-start"),
    path("driver/trips/<uuid:trip_id>/complete/", views.CompleteTripView.as_view(), name="trip-complete"),
    path("driver/trips/<uuid:trip_id>/gps/", views.GPSPingView.as_view(), name="trip-gps"),
    path(
        "driver/trips/<uuid:trip_id>/stops/<uuid:trip_stop_id>/arrived/",
        views.StopArrivedView.as_view(), name="trip-stop-arrived",
    ),
    path(
        "driver/trips/<uuid:trip_id>/passengers/<uuid:trip_passenger_id>/boarded/",
        views.PassengerBoardedView.as_view(), name="trip-passenger-boarded",
    ),
    path(
        "driver/trips/<uuid:trip_id>/passengers/<uuid:trip_passenger_id>/dropped-off/",
        views.PassengerDroppedOffView.as_view(), name="trip-passenger-dropped-off",
    ),
    path(
        "driver/trips/<uuid:trip_id>/passengers/<uuid:trip_passenger_id>/no-show/",
        views.PassengerNoShowView.as_view(), name="trip-passenger-no-show",
    ),

        path(
        "driver/trips/<uuid:trip_id>/passengers/<uuid:trip_passenger_id>/no-show/",
        views.PassengerNoShowView.as_view(), name="trip-passenger-no-show",
    ),

    # Traffic / alternate route
    path("driver/trips/<uuid:trip_id>/traffic/detect/", views.DetectTrafficView.as_view(), name="trip-traffic-detect"),
    path("driver/trips/<uuid:trip_id>/traffic/use-alternate/", views.UseAlternateRouteView.as_view(), name="trip-traffic-alt"),
    path("driver/trips/<uuid:trip_id>/traffic/clear/", views.ClearTrafficView.as_view(), name="trip-traffic-clear"),

        # Organization
    path("org/dashboard/", views.OrgDashboardMetricsView.as_view(), name="org-dashboard"),
    path("org/fleet/live/", views.OrgLiveFleetView.as_view(), name="org-fleet-live"),

]

