from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, ParseError, PermissionDenied

_serializer = URLSafeTimedSerializer(settings.OWNER_LINK_SECRET, salt="owner-response-link")


# ---------------------------------------------------------------------------
# Real per-user authentication (replaces the old shared ADMIN_API_KEY model).
# Login issues a DRF auth token (see views.login_view); every subsequent request
# sends it as `Authorization: Token <key>`, which DRF's TokenAuthentication (wired
# in settings.REST_FRAMEWORK) verifies automatically and populates request.user
# before your view code ever runs — require_admin/require_owner_access below just
# check what DRF already resolved, they don't do any token parsing themselves.
# ---------------------------------------------------------------------------

def require_admin(request):
    """Admin-only routes: real login required, and the account must be staff."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_staff):
        raise AuthenticationFailed("Admin login required for this action.")


def require_owner_access(request, server):
    """
    Routes an authenticated owner can call for their own server(s) — staff can
    access any server too (useful for admins double-checking an owner's view).
    """
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        raise AuthenticationFailed("Login required.")
    if user.is_staff:
        return
    if not user.email or user.email.lower() != (server.owner_email or "").lower():
        raise PermissionDenied("You don't have access to this server.")


# ---------------------------------------------------------------------------
# Signed, expiring links for the no-login email flow. A token can now cover ONE
# or SEVERAL servers (a digest reminder), so it always carries a list — a single
# server's link is just a list of length 1. This is unrelated to the real-account
# auth above; the two flows coexist deliberately (see Technical Architecture notes
# in the README on why: a login-free one-click path stays valuable even once real
# accounts exist, since not every owner will want to remember a password just to
# reply to one reminder).
# ---------------------------------------------------------------------------

def make_owner_link_token(server_ids) -> str:
    ids = list(server_ids) if not isinstance(server_ids, int) else [server_ids]
    return _serializer.dumps({"server_ids": ids})


def verify_owner_link_token(token: str):
    try:
        data = _serializer.loads(token, max_age=settings.OWNER_LINK_MAX_AGE_SECONDS)
    except SignatureExpired:
        raise ParseError("This response link has expired. Ask infra ops to resend a reminder.")
    except BadSignature:
        raise ParseError("Invalid response link.")
    ids = data.get("server_ids")
    if ids is None and "server_id" in data:  # tolerate old single-id tokens still in flight
        ids = [data["server_id"]]
    return ids or []


def build_response_link(server_ids) -> str:
    token = make_owner_link_token(server_ids)
    return f"{settings.FRONTEND_BASE_URL}/owner-response?token={token}"
