import logging

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name="servers_app.tasks.send_reminder_email")
def send_reminder_email(server_id: int, sent_by: str = "admin"):
    from .models import Server, Reminder, ThresholdConfig
    from .security import build_response_link

    try:
        server = Server.objects.get(pk=server_id)
    except Server.DoesNotExist:
        logger.warning("send_reminder_email: server %s not found", server_id)
        return

    Reminder.objects.create(server=server, sent_by=sent_by)
    cfg = ThresholdConfig.get_or_create_singleton()

    response_link = build_response_link(server.id)
    body = cfg.email_template.format(
        owner=server.owner, server=server.name, application=server.application,
        environment=server.environment, cpu=server.cpu_pct, memory=server.memory_pct,
        response_link=response_link,
    )

    # Uses Django's console email backend in dev (no SMTP_HOST set) so reminders are
    # still visible end-to-end without a real mail server — see settings.py.
    send_mail(
        subject=f"Utilization review needed: {server.name}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        # recipient_list=[server.owner_email],
        recipient_list=[settings.DEFAULT_TO_EMAIL],  # added for testing
        fail_silently=False,
    )
    return {"server_id": server_id, "sent_to": server.owner_email}


@shared_task(name="servers_app.tasks.send_reminder_digest_email")
def send_reminder_digest_email(owner_email: str, server_ids: list, sent_by: str = "admin", digest_id: str = None):
    """
    One email covering several servers for the same owner, instead of one email per
    server. Still creates one Reminder row per server (so per-server "reminders sent"
    counts and the needs_reminder 30-day clock stay accurate) — they just all share
    the same digest_id and were the result of a single actual email being sent.
    """
    from .models import Server, Reminder, ThresholdConfig
    from .security import build_response_link

    servers = list(Server.objects.filter(pk__in=server_ids))
    if not servers:
        logger.warning("send_reminder_digest_email: none of %s found", server_ids)
        return

    for s in servers:
        Reminder.objects.create(server=s, sent_by=sent_by, digest_id=digest_id)

    cfg = ThresholdConfig.get_or_create_singleton()
    response_link = build_response_link([s.id for s in servers])

    lines = []
    for s in servers:
        storage_note = f" / {s.storage_pct}% storage" if s.storage_pct is not None else ""
        lines.append(f"- {s.name} ({s.application}, {s.environment}): {s.cpu_pct}% CPU / {s.memory_pct}% memory{storage_note}")
    server_list = "\n".join(lines)

    body = cfg.email_template_digest.format(
        owner=servers[0].owner, count=len(servers), server_list=server_list, response_link=response_link,
    )

    send_mail(
        subject=f"Utilization review needed: {len(servers)} servers",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        # recipient_list=[owner_email],
        recipient_list=[settings.DEFAULT_TO_EMAIL],  # added for testing
        fail_silently=False,
    )
    return {"owner_email": owner_email, "server_ids": [s.id for s in servers], "digest_id": digest_id}


@shared_task(name="servers_app.tasks.flag_escalations")
def flag_escalations():
    """
    Daily check: underutilized servers with 2+ reminders and no owner response.
    In Phase 1 this just logs; wire it to Slack/Teams/email-to-management in Phase 2
    (see Technical Architecture doc, §6).
    """
    from .models import Server

    servers = Server.objects.all().prefetch_related("reminders", "responses")
    escalations = [
        s for s in servers
        if s.status == "Underutilized" and s.reminders.count() >= 2 and not s.responses.exists()
    ]
    if escalations:
        names = ", ".join(s.name for s in escalations)
        logger.warning("ESCALATION: %d server(s) need follow-up: %s", len(escalations), names)
        # added for testing in local
        body = (
            f"Hi,\n\nOur records show {len(escalations)} server(s) need follow-up: {names}"
            f"\n\nThanks,\nInfrastructure Operations"
        )
        send_mail(
            subject=f"ESCALATION: {len(escalations)} server(s) need follow-up",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_TO_EMAIL],
            fail_silently=False,
        )
    return {"escalation_count": len(escalations)}
