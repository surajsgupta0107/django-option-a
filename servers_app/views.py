import csv
import datetime as dt

from django.http import HttpResponse
from django.db.models import Q
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response as DRFResponse
from rest_framework.exceptions import NotFound, ValidationError

from .models import Server, UtilizationSnapshot, Reminder, Response, ThresholdConfig
from .serializers import ServerSerializer, ThresholdConfigSerializer, ResponseSubmitSerializer
from .security import require_admin, verify_owner_link_token
from .importer import parse_upload
from .tasks import send_reminder_email
from .services import compute_kpis


@api_view(["GET"])
def list_servers(request):
    qs = Server.objects.all().prefetch_related("reminders", "responses")

    application = request.query_params.get("application")
    owner = request.query_params.get("owner")
    environment = request.query_params.get("environment")
    company = request.query_params.get("company")
    status_filter = request.query_params.get("status")
    search = request.query_params.get("search")
    needs_reminder_only = request.query_params.get("needs_reminder") in ("1", "true", "True")

    if application:
        qs = qs.filter(application=application)
    if owner:
        qs = qs.filter(owner=owner)
    if environment:
        qs = qs.filter(environment=environment)
    if company:
        qs = qs.filter(company=company)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(application__icontains=search) |
            Q(owner__icontains=search) | Q(company__icontains=search)
        )

    servers = list(qs)
    if status_filter:
        servers = [s for s in servers if s.status == status_filter]
    if needs_reminder_only:
        servers = [s for s in servers if s.needs_reminder]

    data = ServerSerializer(servers, many=True).data
    return DRFResponse({"total": len(data), "items": data})


@api_view(["GET"])
def get_server(request, server_id):
    try:
        server = Server.objects.prefetch_related("reminders", "responses").get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")
    return DRFResponse(ServerSerializer(server).data)


@api_view(["GET"])
def filter_options(request):
    return DRFResponse({
        "applications": sorted(set(Server.objects.values_list("application", flat=True))),
        "owners": sorted(set(Server.objects.values_list("owner", flat=True))),
        "environments": sorted(set(Server.objects.values_list("environment", flat=True))),
        "companies": sorted({c for c in Server.objects.values_list("company", flat=True) if c}),
    })


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload_servers(request):
    require_admin(request)
    file = request.FILES.get("file")
    if not file:
        raise ValidationError("No file provided")

    try:
        records = parse_upload(file.name, file.read())
    except Exception as e:
        raise ValidationError(f"Could not parse file: {e}")

    if not records:
        raise ValidationError("No usable rows found in that file")

    batch_id = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")

    # Replace-all-on-upload for Phase 1 simplicity (matches the FastAPI backend and prototype).
    Server.objects.all().delete()

    errors = []
    imported = 0
    for rec in records:
        try:
            server = Server.objects.create(**rec)
            UtilizationSnapshot.objects.create(
                server=server, cpu_pct=server.cpu_pct, memory_pct=server.memory_pct,
                storage_pct=server.storage_pct, import_batch_id=batch_id,
            )
            imported += 1
        except Exception as e:
            errors.append(f"{rec.get('name', '?')}: {e}")

    return DRFResponse({"imported": imported, "skipped": len(records) - imported, "errors": errors})


@api_view(["GET"])
def export_csv(request):
    servers = Server.objects.all().prefetch_related("reminders", "responses")
    application = request.query_params.get("application")
    if application:
        servers = servers.filter(application=application)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=server-utilization-export.csv"
    writer = csv.writer(response)
    writer.writerow([
        "Server Name", "Application", "Company", "Owner", "Owner Email", "Environment",
        "CPU %", "Memory %", "Storage %", "Status", "Reminders Sent", "Last Reminder", "Owner Response",
    ])
    for s in servers:
        last_reminder = s.reminders.order_by("-sent_at").first()
        last_response = s.responses.order_by("-submitted_at").first()
        writer.writerow([
            s.name, s.application, s.company or "", s.owner, s.owner_email, s.environment,
            s.cpu_pct, s.memory_pct, s.storage_pct if s.storage_pct is not None else "",
            s.status, s.reminders.count(), last_reminder.sent_at if last_reminder else "",
            last_response.decision if last_response else "",
        ])
    return response


@api_view(["GET", "PUT"])
def thresholds(request):
    cfg = ThresholdConfig.get_or_create_singleton()
    if request.method == "GET":
        return DRFResponse(ThresholdConfigSerializer(cfg).data)

    require_admin(request)
    serializer = ThresholdConfigSerializer(cfg, data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return DRFResponse(serializer.data)


@api_view(["POST"])
def send_reminder_single(request, server_id):
    require_admin(request)
    try:
        Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")
    sent_by = request.data.get("sent_by", "admin")
    send_reminder_email.delay(server_id, sent_by)
    return DRFResponse({"queued": True, "server_id": server_id})


@api_view(["POST"])
def send_reminder_bulk(request):
    require_admin(request)
    server_ids = request.data.get("server_ids", [])
    sent_by = request.data.get("sent_by", "admin")
    valid_ids = list(Server.objects.filter(pk__in=server_ids).values_list("id", flat=True))
    for sid in valid_ids:
        send_reminder_email.delay(sid, sent_by)
    return DRFResponse({"queued": len(valid_ids), "server_ids": valid_ids})


@api_view(["GET"])
def lookup_by_token(request):
    token = request.query_params.get("token")
    server_id = verify_owner_link_token(token)
    try:
        server = Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")
    return DRFResponse(ServerSerializer(server).data)


@api_view(["GET"])
def lookup_by_server_id_dev(request, server_id):
    """
    Dev/demo convenience only: lets the Owner Portal list servers without a token,
    matching the prototype's "pick your server" dropdown. Real Phase 1 usage is via
    the emailed token link (/api/responses/lookup); gate or remove this once real
    owner auth is decided (see Technical Architecture doc, §7).
    """
    try:
        server = Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")
    return DRFResponse(ServerSerializer(server).data)


@api_view(["POST"])
def submit_response_dev(request, server_id):
    """Dev/demo counterpart to submit_response (token-based) — see lookup_by_server_id_dev docstring."""
    try:
        server = Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")

    serializer = ResponseSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data
    Response.objects.create(
        server=server, decision=d["decision"], comment=d.get("comment", ""),
        responded_by_name=d.get("responded_by_name") or server.owner,
        responded_by_email=d.get("responded_by_email") or server.owner_email,
    )
    return DRFResponse({"submitted": True})


@api_view(["POST"])
def submit_response(request):
    token = request.query_params.get("token")
    server_id = verify_owner_link_token(token)
    try:
        server = Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")

    serializer = ResponseSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data
    Response.objects.create(
        server=server, decision=d["decision"], comment=d.get("comment", ""),
        responded_by_name=d.get("responded_by_name") or server.owner,
        responded_by_email=d.get("responded_by_email") or server.owner_email,
    )
    return DRFResponse({"submitted": True})


@api_view(["GET"])
def dashboard_kpis(request):
    servers = list(Server.objects.all().prefetch_related("reminders", "responses"))
    return DRFResponse(compute_kpis(servers))


@api_view(["GET"])
def health(request):
    return DRFResponse({"status": "ok"})
