from django.urls import path
from . import views

urlpatterns = [
    path("health", views.health),

    path("auth/login", views.login_view),
    path("auth/logout", views.logout_view),
    path("auth/me", views.me_view),

    path("servers", views.list_servers),
    path("servers/upload", views.upload_servers),
    path("servers/export/csv", views.export_csv),

    path("uploads", views.list_uploaded_sheets),
    path("uploads/<int:sheet_id>/download", views.download_uploaded_sheet),
    path("uploads/compare", views.compare_uploaded_sheets),

    path("servers/meta/filters", views.filter_options),
    path("servers/<int:server_id>", views.get_server),

    path("thresholds", views.thresholds),

    path("reminders/server/<int:server_id>", views.send_reminder_single),
    path("reminders/bulk", views.send_reminder_bulk),

    path("responses/lookup", views.lookup_by_token),
    path("responses/submit", views.submit_response),
    path("responses/by-server-id/<int:server_id>", views.lookup_by_server_id_dev),
    path("responses/submit-dev/<int:server_id>", views.submit_response_dev),

    # Real owner-account access — "My Servers" — separate from the token-link flow above.
    path("my/servers", views.my_servers_view),
    path("my/servers/<int:server_id>/respond", views.my_respond_view),

    path("dashboard/kpis", views.dashboard_kpis),
]
