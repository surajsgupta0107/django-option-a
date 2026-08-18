import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("server_utilization")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# run "celery -A config beat --loglevel=info -S django_celery_beat.schedulers:DatabaseScheduler" to test
# app.conf.beat_schedule = {
#     "flag-escalations-daily": {
#         "task": "servers_app.tasks.flag_escalations",
#         "schedule": crontab(hour=7, minute=0),
#     },
# }
# added for testing in local, technique 1
app.conf.beat_schedule = {
    "flag-escalations-every-few-minutes": {
        "task": "servers_app.tasks.flag_escalations",
        # "schedule": crontab(minute="*/1"),  # every 1 minutes
        # "schedule": crontab(minute="*/2"),  # every 2 minutes
        # "schedule": crontab(minute="*/5"),  # every 5 minutes
        "schedule": crontab(minute="*/10"),  # every 10 minutes
    },
}
# # added for testing in local, technique 2
# app.conf.beat_schedule = {
#     "flag-escalations-every-2-minutes": {
#         "task": "servers_app.tasks.flag_escalations",
#         "schedule": timedelta(minutes=2),  # every 2 minutes
#     },
# }

# # Task routing, added for testing in local,
# # run "celery -A config worker --loglevel=info --pool=solo -Q cloud_queue" to test
# # run "celery -A config worker --loglevel=info --pool=solo --queues=cloud_queue" to test
# app.conf.task_routes = {
#     'servers_app.tasks.send_reminder_email': {
#         'queue': 'cloud_queue'
#     },  # Route 'servers_app.tasks.send_reminder_email' tasks to 'cloud_queue'
# }

