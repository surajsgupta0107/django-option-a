from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, ParseError

_serializer = URLSafeTimedSerializer(settings.OWNER_LINK_SECRET, salt="owner-response-link")


def require_admin(request):
    """
    Phase 1 stand-in for real SSO/OIDC (see Technical Architecture doc, §5).
    Call this at the top of any admin-only view. Swap for DRF's permission
    classes wired to an OIDC backend when integrating company SSO.
    """
    key = request.headers.get("X-API-Key", "")
    if key != settings.ADMIN_API_KEY:
        raise AuthenticationFailed("Invalid or missing API key")


def make_owner_link_token(server_id: int) -> str:
    return _serializer.dumps({"server_id": server_id})


def verify_owner_link_token(token: str) -> int:
    try:
        data = _serializer.loads(token, max_age=settings.OWNER_LINK_MAX_AGE_SECONDS)
    except SignatureExpired:
        raise ParseError("This response link has expired. Ask infra ops to resend a reminder.")
    except BadSignature:
        raise ParseError("Invalid response link.")
    return data["server_id"]


def build_response_link(server_id: int) -> str:
    token = make_owner_link_token(server_id)
    return f"{settings.FRONTEND_BASE_URL}/owner-response?token={token}"
