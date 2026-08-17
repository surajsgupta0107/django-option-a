from django.contrib import admin
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
    list_display = ("server", "sent_at", "sent_by")


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ("server", "decision", "submitted_at", "responded_by_name")


@admin.register(ThresholdConfig)
class ThresholdConfigAdmin(admin.ModelAdmin):
    list_display = ("cpu_threshold", "memory_threshold", "storage_threshold", "rule_mode")


admin.site.register(UtilizationSnapshot)
