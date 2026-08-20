from django.db import models


class ThresholdConfig(models.Model):
    """Singleton row (pk=1) holding the current underutilization rule."""
    RULE_MODE_CHOICES = [("any", "Any enabled metric"), ("all", "All enabled metrics")]

    cpu_threshold = models.FloatField(default=20)
    memory_threshold = models.FloatField(default=25)
    storage_threshold = models.FloatField(default=30)
    cpu_enabled = models.BooleanField(default=True)
    memory_enabled = models.BooleanField(default=True)
    storage_enabled = models.BooleanField(default=False)
    rule_mode = models.CharField(max_length=10, choices=RULE_MODE_CHOICES, default="any")
    overutilized_ceiling = models.FloatField(default=85)
    email_template = models.TextField(default=(
        "Hi {owner},\n\nOur records show {server} ({application}, {environment}) has been "
        "running at {cpu}% CPU / {memory}% memory utilization. Since this is below our "
        "efficiency threshold, could you confirm whether the current allocation is still "
        "required?\n\nYou can respond here: {response_link}\n\nThanks,\nInfrastructure Operations"
    ))
    email_template_digest = models.TextField(default=(
        "Hi {owner},\n\nOur records show {count} of your servers are running below our "
        "efficiency threshold:\n\n{server_list}\n\nCould you confirm whether each allocation "
        "is still required? You can review and respond to all of them here:\n{response_link}"
        "\n\nThanks,\nInfrastructure Operations"
    ))
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_or_create_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={})
        return obj


class Server(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    application = models.CharField(max_length=255, default="Unassigned")
    owner = models.CharField(max_length=255, default="Unassigned")
    owner_email = models.EmailField(default="unknown@company.com")
    company = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    os = models.CharField(max_length=255, null=True, blank=True)
    environment = models.CharField(max_length=100, default="Production")

    cpu_pct = models.FloatField(default=0)
    memory_pct = models.FloatField(default=0)
    storage_pct = models.FloatField(null=True, blank=True)  # null = not tracked in source data

    cpu_allocated = models.FloatField(null=True, blank=True)
    mem_allocated_gb = models.FloatField(null=True, blank=True)
    storage_allocated_gb = models.FloatField(null=True, blank=True)

    reclaimable_vcpu = models.FloatField(null=True, blank=True)
    reclaimable_memory_gb = models.FloatField(null=True, blank=True)

    source = models.CharField(max_length=50, default="upload")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def status(self):
        cfg = ThresholdConfig.get_or_create_singleton()
        checks = []
        if cfg.cpu_enabled:
            checks.append(self.cpu_pct < cfg.cpu_threshold)
        if cfg.memory_enabled:
            checks.append(self.memory_pct < cfg.memory_threshold)
        if cfg.storage_enabled and self.storage_pct is not None:
            checks.append(self.storage_pct < cfg.storage_threshold)

        is_under = any(checks) if cfg.rule_mode == "any" else (all(checks) if checks else False)
        is_over = (
            self.cpu_pct > cfg.overutilized_ceiling
            or self.memory_pct > cfg.overutilized_ceiling
            or (self.storage_pct is not None and self.storage_pct > cfg.overutilized_ceiling)
        )
        if is_under:
            return "Underutilized"
        if is_over:
            return "Overutilized"
        return "Optimal"

    @property
    def needs_reminder(self):
        import datetime as dt
        if self.status != "Underutilized":
            return False
        if self.responses.exists():
            return False
        last = self.reminders.order_by("-sent_at").first()
        if not last:
            return True
        return (dt.datetime.now(dt.timezone.utc) - last.sent_at).days > 30


class UtilizationSnapshot(models.Model):
    """One row per server per import batch — preserves history across re-uploads."""
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="snapshots")
    captured_at = models.DateTimeField(auto_now_add=True)
    cpu_pct = models.FloatField()
    memory_pct = models.FloatField()
    storage_pct = models.FloatField(null=True, blank=True)
    import_batch_id = models.CharField(max_length=64, null=True, blank=True)


class Reminder(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="reminders")
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.CharField(max_length=255, null=True, blank=True)
    template_version = models.CharField(max_length=50, default="v1")
    # Set when this reminder was part of a single consolidated email covering several
    # servers for the same owner (see servers_app/tasks.py's send_reminder_digest_email).
    # Every Reminder row from that one email shares this same value, so "how many separate
    # emails has this owner received" and "how many servers were flagged" stay distinguishable.
    digest_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)


class Response(models.Model):
    DECISION_CHOICES = [
        ("keep", "Hardware still required"),
        ("downsize", "Can be downsized"),
        ("decommission", "Can be decommissioned"),
    ]
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="responses")
    submitted_at = models.DateTimeField(auto_now_add=True)
    decision = models.CharField(max_length=50, choices=DECISION_CHOICES)
    comment = models.TextField(null=True, blank=True)
    responded_by_name = models.CharField(max_length=255, null=True, blank=True)
    responded_by_email = models.EmailField(null=True, blank=True)
