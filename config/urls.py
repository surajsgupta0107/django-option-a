from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("servers_app.urls")),
    # The built React app, served as a static bundle through this one view.
    path("", TemplateView.as_view(template_name="react_app.html"), name="react-app"),
    # Same shell — main.jsx inspects the URL client-side and mounts the standalone
    # OwnerResponsePage instead of the admin App when the path is this one. This is
    # the URL build_response_link() (servers_app/security.py) puts in reminder emails.
    # Any future SPA sub-page would need the same treatment: a route here that serves
    # the same template, since Django itself has no notion of client-side routes.
    path("owner-response", TemplateView.as_view(template_name="react_app.html"), name="owner-response"),
]
