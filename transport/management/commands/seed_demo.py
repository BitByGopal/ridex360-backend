"""
Seeds realistic demo data modeled on the RideX360 V1 target customer:
a private school (Meridian-style) with branches, a bus route, students,
parents and a driver -- so the API and mobile app have something real
to point at immediately.

Run with: python manage.py seed_demo
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from transport.models import (
    Branch, Organization, Passenger, Route, Stop, Trip, TripPassenger,
    TripStop, Vehicle,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo data: one school organization, one branch, one route, passengers, a driver, and today's trip."

    def handle(self, *args, **options):
        org, _ = Organization.objects.get_or_create(
            name="Meridian Schools", defaults={"org_type": "school", "city": "Hyderabad"}
        )
        branch, _ = Branch.objects.get_or_create(
            organization=org, name="Banjara Hills Branch", defaults={"address": "Banjara Hills, Hyderabad"}
        )

        vehicle, _ = Vehicle.objects.get_or_create(
            organization=org, branch=branch, label="Bus 12",
            defaults={"registration_number": "TS09EA1234", "capacity": 40},
        )

        driver, _ = User.objects.get_or_create(
            username="driver1",
            defaults={"first_name": "Ramesh", "last_name": "Kumar", "role": "driver",
                      "organization": org, "branch": branch, "phone": "9800000001"},
        )
        driver.set_password("ridex360demo")
        driver.save()

        route, _ = Route.objects.get_or_create(
            organization=org, branch=branch, name="Route A -- Main Road Line",
            route_type="morning", defaults={"default_vehicle": vehicle, "default_driver": driver},
        )

        stops_data = [
            (1, "Main Road Stop", 17.4126, 78.4483),
            (2, "Jubilee Hills Check Post", 17.4239, 78.4738),
            (3, "Road No. 12 Junction", 17.4180, 78.4100),
            (4, "Meridian Schools -- Banjara Hills", 17.4065, 78.4489),
        ]
        stops = {}
        for seq, name, lat, lng in stops_data:
            stop, _ = Stop.objects.get_or_create(
                route=route, sequence=seq, defaults={"name": name, "latitude": lat, "longitude": lng}
            )
            stops[seq] = stop

        parents_and_kids = [
            ("parent1", "Anjali", "Mehta", "Aarav Mehta", "Grade 4B", 1),
            ("parent2", "Suresh", "Sharma", "Diya Sharma", "Grade 2A", 1),
            ("parent3", "Kavita", "Rao", "Kabir Rao", "Grade 5C", 2),
            ("parent4", "Rajiv", "Verma", "Ishaan Verma", "Grade 3A", 2),
            ("parent5", "Meena", "Nair", "Myra Nair", "Grade 1B", 3),
        ]

        passengers = []
        for username, first, last, child_name, grade, stop_seq in parents_and_kids:
            parent, _ = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "role": "parent", "phone": "9800000000"},
            )
            parent.set_password("ridex360demo")
            parent.save()

            passenger, _ = Passenger.objects.get_or_create(
                organization=org, branch=branch, full_name=child_name,
                defaults={"detail": grade, "pickup_stop": stops[stop_seq]},
            )
            passenger.guardians.add(parent)
            passengers.append(passenger)

        trip, _ = Trip.objects.get_or_create(
            route=route, date=date.today(),
            defaults={"vehicle": vehicle, "driver": driver, "status": "scheduled"},
        )

        for stop in stops.values():
            TripStop.objects.get_or_create(trip=trip, stop=stop)

        for passenger in passengers:
            TripPassenger.objects.get_or_create(trip=trip, passenger=passenger)

        self.stdout.write(self.style.SUCCESS(
            "\nSeeded demo data:\n"
            f"  Organization: {org.name}\n"
            f"  Branch:       {branch.name}\n"
            f"  Route:        {route.name} ({len(stops)} stops)\n"
            f"  Passengers:   {len(passengers)}\n"
            f"  Trip today:   {trip}\n\n"
            "Login credentials (all passwords: ridex360demo):\n"
            "  Driver:  driver1\n"
            "  Parents: parent1, parent2, parent3, parent4, parent5\n"
        ))
