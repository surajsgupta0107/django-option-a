from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("servers_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="reminder",
            name="digest_id",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="thresholdconfig",
            name="email_template_digest",
            field=models.TextField(default=(
                "Hi {owner},\n\nOur records show {count} of your servers are running below our "
                "efficiency threshold:\n\n{server_list}\n\nCould you confirm whether each allocation "
                "is still required? You can review and respond to all of them here:\n{response_link}"
                "\n\nThanks,\nInfrastructure Operations"
            )),
        ),
    ]
