from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Server, UtilizationSnapshot, Reminder, Response, ThresholdConfig


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ("name", "application", "owner", "company", "environment", "cpu_pct", "memory_pct", "status")
    list_filter = ("environment", "application", "company")
    search_fields = ("name", "application", "owner", "company")

    def status(self, obj):
        return obj.status


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("server", "sent_at", "sent_by", "digest_id")
    list_filter = ("sent_by",)


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ("server", "decision", "submitted_at", "responded_by_name")


@admin.register(ThresholdConfig)
class ThresholdConfigAdmin(admin.ModelAdmin):
    list_display = ("cpu_threshold", "memory_threshold", "storage_threshold", "rule_mode")


admin.site.register(UtilizationSnapshot)


# Re-register User with email + staff status visible in the list view — that's the
# whole account-creation workflow for this app: create a user here, check "Staff
# status" for an Admin account, leave it unchecked and set Email to match a Server's
# owner_email for an Owner account (see servers_app/security.py's require_owner_access
# and the /api/my/servers endpoint, which match on that email).
admin.site.unregister(User)


@admin.register(User)
class RightSizeUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_staff", "is_active", "last_login")
    list_filter = ("is_staff", "is_active")
    search_fields = ("username", "email")
