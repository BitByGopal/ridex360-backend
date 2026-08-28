"""
Creates a superuser from DJANGO_SUPERUSER_* environment variables, but
only if one with that username doesn't already exist. Safe to run on
every deploy (idempotent) -- this is how we get admin access on Render's
free tier without needing interactive shell access.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Create a superuser from DJANGO_SUPERUSER_* env vars if one doesn't already exist."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                "DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD not set -- skipping."
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Superuser '{username}' already exists -- skipping.")
            return

        User.objects.create_superuser(username=username, email=email, password=password, role="org_admin")
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))