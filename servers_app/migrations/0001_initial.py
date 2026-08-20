from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ThresholdConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cpu_threshold", models.FloatField(default=20)),
                ("memory_threshold", models.FloatField(default=25)),
                ("storage_threshold", models.FloatField(default=30)),
                ("cpu_enabled", models.BooleanField(default=True)),
                ("memory_enabled", models.BooleanField(default=True)),
                ("storage_enabled", models.BooleanField(default=False)),
                ("rule_mode", models.CharField(choices=[("any", "Any enabled metric"), ("all", "All enabled metrics")], default="any", max_length=10)),
                ("overutilized_ceiling", models.FloatField(default=85)),
                ("email_template", models.TextField(default="Hi {owner},\n\nOur records show {server} ({application}, {environment}) has been running at {cpu}% CPU / {memory}% memory utilization. Since this is below our efficiency threshold, could you confirm whether the current allocation is still required?\n\nYou can respond here: {response_link}\n\nThanks,\nInfrastructure Operations")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Server",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=255)),
                ("application", models.CharField(default="Unassigned", max_length=255)),
                ("owner", models.CharField(default="Unassigned", max_length=255)),
                ("owner_email", models.EmailField(default="unknown@company.com", max_length=254)),
                ("company", models.CharField(blank=True, max_length=255, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("os", models.CharField(blank=True, max_length=255, null=True)),
                ("environment", models.CharField(default="Production", max_length=100)),
                ("cpu_pct", models.FloatField(default=0)),
                ("memory_pct", models.FloatField(default=0)),
                ("storage_pct", models.FloatField(blank=True, null=True)),
                ("cpu_allocated", models.FloatField(blank=True, null=True)),
                ("mem_allocated_gb", models.FloatField(blank=True, null=True)),
                ("storage_allocated_gb", models.FloatField(blank=True, null=True)),
                ("reclaimable_vcpu", models.FloatField(blank=True, null=True)),
                ("reclaimable_memory_gb", models.FloatField(blank=True, null=True)),
                ("source", models.CharField(default="upload", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="UtilizationSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
                ("cpu_pct", models.FloatField()),
                ("memory_pct", models.FloatField()),
                ("storage_pct", models.FloatField(blank=True, null=True)),
                ("import_batch_id", models.CharField(blank=True, max_length=64, null=True)),
                ("server", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="snapshots", to="servers_app.server")),
            ],
        ),
        migrations.CreateModel(
            name="Reminder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                ("sent_by", models.CharField(blank=True, max_length=255, null=True)),
                ("template_version", models.CharField(default="v1", max_length=50)),
                ("server", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reminders", to="servers_app.server")),
            ],
        ),
        migrations.CreateModel(
            name="Response",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("decision", models.CharField(choices=[("keep", "Hardware still required"), ("downsize", "Can be downsized"), ("decommission", "Can be decommissioned")], max_length=50)),
                ("comment", models.TextField(blank=True, null=True)),
                ("responded_by_name", models.CharField(blank=True, max_length=255, null=True)),
                ("responded_by_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("server", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="responses", to="servers_app.server")),
            ],
        ),
    ]
