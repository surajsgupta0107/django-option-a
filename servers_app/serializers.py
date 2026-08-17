from rest_framework import serializers
from .models import Server, Reminder, Response, ThresholdConfig


class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = ["id", "sent_at", "sent_by"]


class ResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ["id", "submitted_at", "decision", "comment", "responded_by_name"]


class ServerSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    reminders_sent = serializers.SerializerMethodField()
    last_reminder_at = serializers.SerializerMethodField()
    owner_responded = serializers.SerializerMethodField()
    latest_response = serializers.SerializerMethodField()
    reminders = ReminderSerializer(many=True, read_only=True)
    responses = ResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Server
        fields = [
            "id", "name", "application", "owner", "owner_email", "company", "description", "os",
            "environment", "cpu_pct", "memory_pct", "storage_pct", "cpu_allocated", "mem_allocated_gb",
            "storage_allocated_gb", "reclaimable_vcpu", "reclaimable_memory_gb", "status",
            "reminders_sent", "last_reminder_at", "owner_responded", "latest_response",
            "reminders", "responses",
        ]

    def get_reminders_sent(self, obj):
        return obj.reminders.count()

    def get_last_reminder_at(self, obj):
        last = obj.reminders.order_by("-sent_at").first()
        return last.sent_at if last else None

    def get_owner_responded(self, obj):
        return obj.responses.exists()

    def get_latest_response(self, obj):
        last = obj.responses.order_by("-submitted_at").first()
        return last.decision if last else None


class ThresholdConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThresholdConfig
        fields = [
            "cpu_threshold", "memory_threshold", "storage_threshold",
            "cpu_enabled", "memory_enabled", "storage_enabled", "rule_mode",
            "overutilized_ceiling", "email_template",
        ]


class ResponseSubmitSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["keep", "downsize", "decommission"])
    comment = serializers.CharField(required=False, allow_blank=True)
    responded_by_name = serializers.CharField(required=False, allow_blank=True)
    responded_by_email = serializers.EmailField(required=False, allow_blank=True)
