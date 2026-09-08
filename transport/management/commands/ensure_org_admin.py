"""
Creates an org_admin user from ORG_ADMIN_* environment variables, but
only if one with that username doesn't already exist. Same pattern as
accounts/management/commands/ensure_superuser.py -- safe to run on
every deploy, and doesn't require Render shell access (a paid-plan
feature not available on the free tier).
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from transport.models import Organization

User = get_user_model()


class Command(BaseCommand):
    help = "Create an org_admin user from ORG_ADMIN_* env vars if one doesn't already exist."

    def handle(self, *args, **options):
        username = os.environ.get("ORG_ADMIN_USERNAME")
        password = os.environ.get("ORG_ADMIN_PASSWORD")

        if not username or not password:
            self.stdout.write(self.style.WARNING("ORG_ADMIN_USERNAME / ORG_ADMIN_PASSWORD not set -- skipping."))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"org_admin '{username}' already exists -- skipping.")
            return

        org = Organization.objects.first()
        if org is None:
            self.stdout.write(self.style.WARNING("No Organization exists yet -- run seed_demo first. Skipping."))
            return

        user = User.objects.create_user(username=username, role="org_admin", organization=org)
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Created org_admin '{username}' for {org.name}."))