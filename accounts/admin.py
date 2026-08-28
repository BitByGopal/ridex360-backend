from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "get_full_name", "role", "organization", "branch", "phone", "is_active")
    list_filter = ("role", "organization", "branch", "is_active")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("RideX360", {"fields": ("role", "phone", "organization", "branch")}),
    )
