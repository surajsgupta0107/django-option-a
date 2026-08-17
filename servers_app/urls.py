from django.urls import path
from . import views

urlpatterns = [
    path("health", views.health),
    path("servers", views.list_servers),
    path("servers/upload", views.upload_servers),
    path("servers/export/csv", views.export_csv),
    path("servers/meta/filters", views.filter_options),
    path("servers/<int:server_id>", views.get_server),
    path("thresholds", views.thresholds),
    path("reminders/server/<int:server_id>", views.send_reminder_single),
    path("reminders/bulk", views.send_reminder_bulk),
    path("responses/lookup", views.lookup_by_token),
    path("responses/submit", views.submit_response),
    path("responses/by-server-id/<int:server_id>", views.lookup_by_server_id_dev),
    path("responses/submit-dev/<int:server_id>", views.submit_response_dev),
    path("dashboard/kpis", views.dashboard_kpis),
]
