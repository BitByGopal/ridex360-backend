import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    RideX360's single user model. The 'role' decides which mobile
    screens the frontend shows and which API endpoints are permitted --
    the same account system works whether the org is a school, a
    company, or a hospital; only the role labels displayed change.
    """

    class Role(models.TextChoices):
        PARENT = "parent", "Parent"
        DRIVER = "driver", "Driver"
        ORG_ADMIN = "org_admin", "Organization Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=20, blank=True)

    # An org_admin or driver belongs to one organization/branch.
    # A parent doesn't need this directly -- their org context comes
    # from the passenger(s) they're guardian of, since a parent could
    # in principle have children at more than one branch.
    organization = models.ForeignKey(
        "transport.Organization", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="staff_users",
    )
    branch = models.ForeignKey(
        "transport.Branch", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="staff_users",
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"
