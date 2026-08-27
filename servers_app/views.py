import csv
import datetime as dt
import uuid
import os

from django.http import HttpResponse, FileResponse
from django.db.models import Q
from django.contrib.auth import authenticate, get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response as DRFResponse
from rest_framework.exceptions import NotFound, ValidationError, AuthenticationFailed, PermissionDenied

from .models import Server, UtilizationSnapshot, Reminder, Response, ThresholdConfig, UploadedSheet
from .serializers import ServerSerializer, ThresholdConfigSerializer, ResponseSubmitSerializer
from .security import require_admin, require_owner_access, verify_owner_link_token
from .importer import parse_upload
from .tasks import send_reminder_email, send_reminder_digest_email
from .services import compute_kpis


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@api_view(["POST"])
def login_view(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        raise AuthenticationFailed("Incorrect username or password.")
    token, _ = Token.objects.get_or_create(user=user)
    return DRFResponse({
        "token": token.key,
        "username": user.username,
        "email": user.email,
        "role": "admin" if user.is_staff else "owner",
    })


@api_view(["POST"])
def logout_view(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        Token.objects.filter(user=user).delete()
    return DRFResponse({"loggedOut": True})


@api_view(["GET"])
def me_view(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        raise AuthenticationFailed("Not logged in.")
    return DRFResponse({
        "username": user.username,
        "email": user.email,
        "role": "admin" if user.is_staff else "owner",
    })


# ---------------------------------------------------------------------------
# Servers (admin-facing list/detail/upload/export)
# ---------------------------------------------------------------------------

@api_view(["GET"])
def list_servers(request):
    require_admin(request)
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
    require_admin(request)
    try:
        server = Server.objects.prefetch_related("reminders", "responses").get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")
    return DRFResponse(ServerSerializer(server).data)


@api_view(["GET"])
def filter_options(request):
    require_admin(request)
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
        # records = parse_upload(file.name, file.read())  # old
        content = file.read()
        records = parse_upload(file.name, content)  # new
    except Exception as e:
        raise ValidationError(f"Could not parse file: {e}")

    if not records:
        raise ValidationError("No usable rows found in that file")

    # batch_id = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")  # old
    batch_id = uuid.uuid4().hex  # new

    uploaded_sheet = UploadedSheet.objects.create(
        file=file,
        original_filename=file.name,
        uploaded_by=request.user,
        import_batch_id=batch_id,
    )

    # Replace-all-on-upload for Phase 1 simplicity (matches the FastAPI backend and prototype).
    Server.objects.all().delete()

    errors = []
    imported = 0

    User = get_user_model()

    for rec in records:
        try:
            # -----------------------------------------
            # Create owner user for testing
            # -----------------------------------------
            owner_fullname = str(rec.get("owner", "")).strip()
            if owner_fullname:
                username = "".join(owner_fullname.lower().split())
                email = f"{username}@gmail.com"
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": email,
                    },
                )
                if created:
                    user.set_password("owner")
                    user.save()
            server = Server.objects.create(**rec)
            UtilizationSnapshot.objects.create(
                server=server, cpu_pct=server.cpu_pct, memory_pct=server.memory_pct,
                storage_pct=server.storage_pct, import_batch_id=batch_id,
            )
            imported += 1
        except Exception as e:
            errors.append(f"{rec.get('name', '?')}: {e}")

    uploaded_sheet.imported_rows = imported
    uploaded_sheet.skipped_rows = len(records) - imported
    uploaded_sheet.save(
        update_fields=["imported_rows", "skipped_rows"]
    )

    # return DRFResponse({"imported": imported, "skipped": len(records) - imported, "errors": errors})  # old
    return DRFResponse({
        "imported": imported,
        "skipped": len(records) - imported,
        "errors": errors,
        "sheet_id": uploaded_sheet.id,
        "filename": uploaded_sheet.original_filename,
    })  # new


@api_view(["GET"])
def list_uploaded_sheets(request):
    require_admin(request)

    sheets = UploadedSheet.objects.select_related(
        "uploaded_by"
    ).order_by("-uploaded_at")

    items = []

    for sheet in sheets:
        items.append({
            "id": sheet.id,
            "filename": sheet.original_filename,
            "uploaded_at": sheet.uploaded_at,
            "uploaded_by": (
                sheet.uploaded_by.username
                if sheet.uploaded_by
                else None
            ),
            "imported_rows": sheet.imported_rows,
            "skipped_rows": sheet.skipped_rows,
            "file_size": sheet.file_size,
            "import_batch_id": sheet.import_batch_id,
        })

    return DRFResponse({
        "total": len(items),
        "items": items,
    })


@api_view(["GET"])
def download_uploaded_sheet(request, sheet_id):
    require_admin(request)

    try:
        sheet = UploadedSheet.objects.get(pk=sheet_id)
    except UploadedSheet.DoesNotExist:
        raise NotFound("Uploaded sheet not found")

    if not sheet.file:
        raise NotFound("Uploaded file is missing")

    try:
        sheet.file.open("rb")
    except Exception:
        raise NotFound("Uploaded file could not be opened")

    response = FileResponse(
        sheet.file,
        as_attachment=True,
        filename=sheet.original_filename,
    )

    return response


@api_view(["GET"])
def compare_uploaded_sheets(request):
    require_admin(request)

    sheet_a_id = request.query_params.get("sheet_a")
    sheet_b_id = request.query_params.get("sheet_b")

    sheets = UploadedSheet.objects.all().order_by("-uploaded_at")

    if sheets.count() < 2:
        raise ValidationError(
            "At least two uploaded sheets are required for comparison."
        )

    # ---------------------------------------------------------
    # DEFAULT COMPARISON
    #
    # No IDs supplied:
    #   Sheet A = previous upload
    #   Sheet B = current/latest upload
    #
    # This means Compare Sheets automatically opens with:
    #
    # Previous → immediately previous upload
    # Current  → latest upload
    # ---------------------------------------------------------
    if not sheet_a_id and not sheet_b_id:
        sheet_b = sheets[0]
        sheet_a = sheets[1]

    else:
        if not sheet_a_id or not sheet_b_id:
            raise ValidationError(
                "Both sheet_a and sheet_b are required."
            )

        try:
            sheet_a = UploadedSheet.objects.get(pk=sheet_a_id)
        except UploadedSheet.DoesNotExist:
            raise NotFound("Previous sheet not found.")

        try:
            sheet_b = UploadedSheet.objects.get(pk=sheet_b_id)
        except UploadedSheet.DoesNotExist:
            raise NotFound("Current sheet not found.")

    if sheet_a.id == sheet_b.id:
        raise ValidationError(
            "Please select two different sheets."
        )

    # ---------------------------------------------------------
    # READ BOTH ORIGINAL FILES
    # ---------------------------------------------------------

    try:
        sheet_a.file.open("rb")
        content_a = sheet_a.file.read()

        sheet_b.file.open("rb")
        content_b = sheet_b.file.read()

        records_a = parse_upload(
            sheet_a.original_filename,
            content_a,
        )

        records_b = parse_upload(
            sheet_b.original_filename,
            content_b,
        )

    except Exception as e:
        raise ValidationError(
            f"Could not parse sheets: {e}"
        )

    # ---------------------------------------------------------
    # INDEX BY SERVER NAME
    # ---------------------------------------------------------

    previous_rows = {
        str(row.get("name", "")).strip().lower(): row
        for row in records_a
        if row.get("name")
    }

    current_rows = {
        str(row.get("name", "")).strip().lower(): row
        for row in records_b
        if row.get("name")
    }

    previous_keys = set(previous_rows.keys())
    current_keys = set(current_rows.keys())

    added_keys = current_keys - previous_keys
    removed_keys = previous_keys - current_keys
    common_keys = previous_keys & current_keys

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    def number(value):
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def diff(current, previous):
        current_num = number(current)
        previous_num = number(previous)

        if current_num is None or previous_num is None:
            return None

        return round(current_num - previous_num, 2)

    def metric(previous, current):
        return {
            "previous": number(previous),
            "current": number(current),
            "change": diff(current, previous),
        }

    # ---------------------------------------------------------
    # BUILD FULL DETAIL TABLE
    # ---------------------------------------------------------

    details = []

    for key in sorted(previous_keys | current_keys):

        previous = previous_rows.get(key)
        current = current_rows.get(key)

        # -----------------------------------------------------
        # SERVER EXISTS ONLY IN CURRENT
        # -----------------------------------------------------

        if previous is None:
            source = current

            details.append({
                "server_name": source.get("name"),
                "change_type": "added",

                "application": source.get("application"),
                "owner": source.get("owner"),
                "owner_email": source.get("owner_email"),
                "company": source.get("company"),
                "description": source.get("description"),
                "os": source.get("os"),
                "environment": source.get("environment"),

                "cpu": metric(
                    None,
                    source.get("cpu_pct"),
                ),
                "memory": metric(
                    None,
                    source.get("memory_pct"),
                ),
                "storage": metric(
                    None,
                    source.get("storage_pct"),
                ),

                "cpu_allocated": metric(
                    None,
                    source.get("cpu_allocated"),
                ),
                "memory_allocated": metric(
                    None,
                    source.get("mem_allocated_gb"),
                ),
                "storage_allocated": metric(
                    None,
                    source.get("storage_allocated_gb"),
                ),

                "cpu_reclaimable": metric(
                    None,
                    source.get("reclaimable_vcpu"),
                ),
                "memory_reclaimable": metric(
                    None,
                    source.get("reclaimable_memory_gb"),
                ),

                "status": "Added",
            })

            continue

        # -----------------------------------------------------
        # SERVER EXISTS ONLY IN PREVIOUS
        # -----------------------------------------------------

        if current is None:
            source = previous

            details.append({
                "server_name": source.get("name"),
                "change_type": "removed",

                "application": source.get("application"),
                "owner": source.get("owner"),
                "owner_email": source.get("owner_email"),
                "company": source.get("company"),
                "description": source.get("description"),
                "os": source.get("os"),
                "environment": source.get("environment"),

                "cpu": metric(
                    source.get("cpu_pct"),
                    None,
                ),
                "memory": metric(
                    source.get("memory_pct"),
                    None,
                ),
                "storage": metric(
                    source.get("storage_pct"),
                    None,
                ),

                "cpu_allocated": metric(
                    source.get("cpu_allocated"),
                    None,
                ),
                "memory_allocated": metric(
                    source.get("mem_allocated_gb"),
                    None,
                ),
                "storage_allocated": metric(
                    source.get("storage_allocated_gb"),
                    None,
                ),

                "cpu_reclaimable": metric(
                    source.get("reclaimable_vcpu"),
                    None,
                ),
                "memory_reclaimable": metric(
                    source.get("reclaimable_memory_gb"),
                    None,
                ),

                "status": "Removed",
            })

            continue

        # -----------------------------------------------------
        # SERVER EXISTS IN BOTH
        # -----------------------------------------------------

        details.append({
            "server_name": current.get("name"),

            "change_type": (
                "changed"
                if any([
                    previous.get("application") != current.get("application"),
                    previous.get("owner") != current.get("owner"),
                    previous.get("owner_email") != current.get("owner_email"),
                    previous.get("company") != current.get("company"),
                    previous.get("description") != current.get("description"),
                    previous.get("os") != current.get("os"),
                    previous.get("environment") != current.get("environment"),
                    previous.get("cpu_pct") != current.get("cpu_pct"),
                    previous.get("memory_pct") != current.get("memory_pct"),
                    previous.get("storage_pct") != current.get("storage_pct"),
                    previous.get("cpu_allocated") != current.get("cpu_allocated"),
                    previous.get("mem_allocated_gb") != current.get("mem_allocated_gb"),
                    previous.get("storage_allocated_gb") != current.get("storage_allocated_gb"),
                    previous.get("reclaimable_vcpu") != current.get("reclaimable_vcpu"),
                    previous.get("reclaimable_memory_gb") != current.get("reclaimable_memory_gb"),
                ])
                else "unchanged"
            ),

            # -------------------------------------------------
            # NORMAL SERVER FIELDS
            # Current value is shown as the primary value.
            # -------------------------------------------------

            "application": current.get("application"),
            "owner": current.get("owner"),
            "owner_email": current.get("owner_email"),
            "company": current.get("company"),
            "description": current.get("description"),
            "os": current.get("os"),
            "environment": current.get("environment"),

            # -------------------------------------------------
            # UTILIZATION
            # -------------------------------------------------

            "cpu": metric(
                previous.get("cpu_pct"),
                current.get("cpu_pct"),
            ),

            "memory": metric(
                previous.get("memory_pct"),
                current.get("memory_pct"),
            ),

            "storage": metric(
                previous.get("storage_pct"),
                current.get("storage_pct"),
            ),

            # -------------------------------------------------
            # ALLOCATED
            # -------------------------------------------------

            "cpu_allocated": metric(
                previous.get("cpu_allocated"),
                current.get("cpu_allocated"),
            ),

            "memory_allocated": metric(
                previous.get("mem_allocated_gb"),
                current.get("mem_allocated_gb"),
            ),

            "storage_allocated": metric(
                previous.get("storage_allocated_gb"),
                current.get("storage_allocated_gb"),
            ),

            # -------------------------------------------------
            # RECLAIMABLE
            # -------------------------------------------------

            "cpu_reclaimable": metric(
                previous.get("reclaimable_vcpu"),
                current.get("reclaimable_vcpu"),
            ),

            "memory_reclaimable": metric(
                previous.get("reclaimable_memory_gb"),
                current.get("reclaimable_memory_gb"),
            ),

            "status": (
                "Changed"
                if any([
                    previous.get("cpu_pct") != current.get("cpu_pct"),
                    previous.get("memory_pct") != current.get("memory_pct"),
                    previous.get("storage_pct") != current.get("storage_pct"),
                    previous.get("cpu_allocated") != current.get("cpu_allocated"),
                    previous.get("mem_allocated_gb") != current.get("mem_allocated_gb"),
                    previous.get("storage_allocated_gb") != current.get("storage_allocated_gb"),
                    previous.get("reclaimable_vcpu") != current.get("reclaimable_vcpu"),
                    previous.get("reclaimable_memory_gb") != current.get("reclaimable_memory_gb"),
                ])
                else "Unchanged"
            ),
        })

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    added = sum(
        1 for row in details
        if row["change_type"] == "added"
    )

    removed = sum(
        1 for row in details
        if row["change_type"] == "removed"
    )

    changed = sum(
        1 for row in details
        if row["change_type"] == "changed"
    )

    unchanged = sum(
        1 for row in details
        if row["change_type"] == "unchanged"
    )

    return DRFResponse({
        "previous_sheet": {
            "id": sheet_a.id,
            "filename": sheet_a.original_filename,
            "uploaded_at": sheet_a.uploaded_at,
            "rows": len(records_a),
        },

        "current_sheet": {
            "id": sheet_b.id,
            "filename": sheet_b.original_filename,
            "uploaded_at": sheet_b.uploaded_at,
            "rows": len(records_b),
        },

        "summary": {
            "previous_rows": len(records_a),
            "current_rows": len(records_b),
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged": unchanged,
        },

        "details": details,
    })


@api_view(["GET"])
def compare_uploaded_sheets_v1(request):
    require_admin(request)

    sheet_a_id = request.query_params.get("sheet_a")
    sheet_b_id = request.query_params.get("sheet_b")

    if not sheet_a_id or not sheet_b_id:
        raise ValidationError(
            "Both sheet_a and sheet_b are required."
        )

    if sheet_a_id == sheet_b_id:
        raise ValidationError(
            "Please select two different sheets."
        )

    try:
        sheet_a = UploadedSheet.objects.get(pk=sheet_a_id)
    except UploadedSheet.DoesNotExist:
        raise NotFound("Sheet A not found.")

    try:
        sheet_b = UploadedSheet.objects.get(pk=sheet_b_id)
    except UploadedSheet.DoesNotExist:
        raise NotFound("Sheet B not found.")

    try:
        sheet_a.file.open("rb")
        content_a = sheet_a.file.read()

        sheet_b.file.open("rb")
        content_b = sheet_b.file.read()

        records_a = parse_upload(
            sheet_a.original_filename,
            content_a,
        )

        records_b = parse_upload(
            sheet_b.original_filename,
            content_b,
        )

    except Exception as e:
        raise ValidationError(
            f"Could not parse sheets: {e}"
        )

    rows_a = {
        str(row["name"]).strip().lower(): row
        for row in records_a
        if row.get("name")
    }

    rows_b = {
        str(row["name"]).strip().lower(): row
        for row in records_b
        if row.get("name")
    }

    keys_a = set(rows_a)
    keys_b = set(rows_b)

    added = []
    removed = []
    changed = []
    unchanged = []

    compare_fields = [
        "application",
        "owner",
        "owner_email",
        "company",
        "description",
        "environment",
        "cpu_pct",
        "memory_pct",
        "storage_pct",
        "cpu_allocated",
        "mem_allocated_gb",
        "storage_allocated_gb",
        "reclaimable_vcpu",
        "reclaimable_memory_gb",
    ]

    for key in sorted(keys_b - keys_a):
        added.append({
            "server": rows_b[key],
        })

    for key in sorted(keys_a - keys_b):
        removed.append({
            "server": rows_a[key],
        })

    for key in sorted(keys_a & keys_b):
        old_row = rows_a[key]
        new_row = rows_b[key]

        differences = []

        for field in compare_fields:
            old_value = old_row.get(field)
            new_value = new_row.get(field)

            if old_value != new_value:
                differences.append({
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value,
                })

        if differences:
            changed.append({
                "server_name": old_row["name"],
                "changes": differences,
            })
        else:
            unchanged.append({
                "server_name": old_row["name"],
            })

    return DRFResponse({
        "sheet_a": {
            "id": sheet_a.id,
            "filename": sheet_a.original_filename,
            "uploaded_at": sheet_a.uploaded_at,
        },
        "sheet_b": {
            "id": sheet_b.id,
            "filename": sheet_b.original_filename,
            "uploaded_at": sheet_b.uploaded_at,
        },
        "summary": {
            "sheet_a_rows": len(records_a),
            "sheet_b_rows": len(records_b),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    })


@api_view(["GET"])
def export_csv(request):
    require_admin(request)
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
        require_admin(request)
        return DRFResponse(ThresholdConfigSerializer(cfg).data)

    require_admin(request)
    serializer = ThresholdConfigSerializer(cfg, data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return DRFResponse(serializer.data)


# ---------------------------------------------------------------------------
# Reminders — bulk send is now owner-aware: servers belonging to the same owner
# get consolidated into ONE email instead of one-per-server.
# ---------------------------------------------------------------------------

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
    """
    Groups the selected servers by owner_email and sends ONE consolidated email per
    owner who has more than one server in the selection, instead of one email per
    server — see servers_app/tasks.py's send_reminder_digest_email. An owner with only
    one selected server still just gets the normal single-server email; no behavior
    change there.
    """
    require_admin(request)
    server_ids = request.data.get("server_ids", [])
    sent_by = request.data.get("sent_by", "admin")

    servers = list(Server.objects.filter(pk__in=server_ids))
    by_owner = {}
    for s in servers:
        by_owner.setdefault(s.owner_email, []).append(s.id)

    queued_single = 0
    queued_digest = 0
    for owner_email, ids in by_owner.items():
        if len(ids) > 1:
            digest_id = uuid.uuid4().hex[:16]
            send_reminder_digest_email.delay(owner_email, ids, sent_by, digest_id)
            queued_digest += 1
        else:
            send_reminder_email.delay(ids[0], sent_by)
            queued_single += 1

    return DRFResponse({
        "queued": len(servers), "server_ids": [s.id for s in servers],
        "emails_sent": queued_single + queued_digest,
        "digest_emails": queued_digest, "single_emails": queued_single,
    })


# ---------------------------------------------------------------------------
# Owner response via signed link — no login required. Token now covers a LIST of
# server ids (a digest reminder covers several); a single-server link is just a
# list of length 1, so this same pair of endpoints serves both cases.
# ---------------------------------------------------------------------------

@api_view(["GET"])
def lookup_by_token(request):
    token = request.query_params.get("token")
    server_ids = verify_owner_link_token(token)
    servers = list(Server.objects.filter(pk__in=server_ids).prefetch_related("reminders", "responses"))
    if not servers:
        raise NotFound("No servers found for this link.")
    # preserve the token's original order rather than whatever the DB returns
    by_id = {s.id: s for s in servers}
    ordered = [by_id[i] for i in server_ids if i in by_id]
    return DRFResponse({"items": ServerSerializer(ordered, many=True).data})


@api_view(["POST"])
def submit_response(request):
    """
    Body: {"responses": [{"server_id": 1, "decision": "keep", "comment": "..."}, ...]}
    Every server_id must be one of the ids this specific token was issued for — this
    is the actual security boundary (see security.verify_owner_link_token); without
    this check, a token for server A's link could be replayed to respond for any
    other server just by changing the id in the request body.
    """
    token = request.query_params.get("token")
    allowed_ids = set(verify_owner_link_token(token))

    items = request.data.get("responses", [])
    if not items:
        raise ValidationError("No responses provided.")

    created = []
    for item in items:
        server_id = item.get("server_id")
        if server_id not in allowed_ids:
            raise PermissionDenied(f"This link doesn't grant access to server {server_id}.")
        try:
            server = Server.objects.get(pk=server_id)
        except Server.DoesNotExist:
            continue
        serializer = ResponseSubmitSerializer(data=item)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        Response.objects.create(
            server=server, decision=d["decision"], comment=d.get("comment", ""),
            responded_by_name=d.get("responded_by_name") or server.owner,
            responded_by_email=d.get("responded_by_email") or server.owner_email,
        )
        created.append(server_id)

    return DRFResponse({"submitted": True, "server_ids": created})


# ---------------------------------------------------------------------------
# Admin-side demo shortcut — the "Owner Portal" tab's dropdown, for showing the
# workflow to stakeholders without needing a real email round-trip. Requires admin
# login now (previously open) — this is an admin convenience feature, not something
# an anonymous visitor should be able to hit. Real owners use either the emailed
# token link above, or their own account via /api/my/servers below.
# ---------------------------------------------------------------------------

@api_view(["GET"])
def lookup_by_server_id_dev(request, server_id):
    require_admin(request)
    try:
        server = Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")
    return DRFResponse(ServerSerializer(server).data)


@api_view(["POST"])
def submit_response_dev(request, server_id):
    require_admin(request)
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


# ---------------------------------------------------------------------------
# Real owner account access — "My Servers": a logged-in owner's own dashboard,
# scoped to servers where Server.owner_email matches their account email. Staff
# accounts can also hit these (useful for an admin to sanity-check what a specific
# owner sees), scoped the same way rather than seeing everything.
# ---------------------------------------------------------------------------

@api_view(["GET"])
def my_servers_view(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        raise AuthenticationFailed("Login required.")
    if not user.email:
        return DRFResponse({"total": 0, "items": []})
    servers = list(
        Server.objects.filter(owner_email__iexact=user.email).prefetch_related("reminders", "responses")
    )
    # servers = [s for s in servers if s.status == "Underutilized"]  # added for testing in local
    data = ServerSerializer(servers, many=True).data
    return DRFResponse({"total": len(data), "items": data})


@api_view(["POST"])
def my_respond_view(request, server_id):
    try:
        server = Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        raise NotFound("Server not found")
    require_owner_access(request, server)

    serializer = ResponseSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data
    user = request.user
    Response.objects.create(
        server=server, decision=d["decision"], comment=d.get("comment", ""),
        responded_by_name=d.get("responded_by_name") or user.get_full_name() or user.username,
        responded_by_email=d.get("responded_by_email") or user.email or server.owner_email,
    )
    return DRFResponse({"submitted": True})


@api_view(["GET"])
def dashboard_kpis(request):
    require_admin(request)
    servers = list(Server.objects.all().prefetch_related("reminders", "responses"))
    return DRFResponse(compute_kpis(servers))


@api_view(["GET"])
def health(request):
    return DRFResponse({"status": "ok"})
