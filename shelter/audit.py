"""Audit metadata is deliberately independent of source-record lifetimes."""
import uuid
from contextvars import ContextVar
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import AuditEvent

current_request = ContextVar('audit_request', default=None)


class AuditContextMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        request.audit_request_id = str(uuid.uuid4())
        token = current_request.set(request)
        try:
            response = self.get_response(request)
            if response.status_code == 403:
                record('access', 'access.denied', outcome='failure', changes={'route':getattr(getattr(request, 'resolver_match', None), 'url_name', '')})
            return response
        finally: current_request.reset(token)


def record(category, action, *, target=None, changes=None, outcome='success', actor=None, animal_id=None):
    request = current_request.get()
    actor = actor or (getattr(request, 'user', None) if request else None)
    authenticated = actor is not None and actor.is_authenticated
    return AuditEvent.objects.create(
        category=category, action=action, outcome=outcome,
        actor_id_snapshot=actor.pk if authenticated else None,
        actor_name=(actor.full_name or actor.username)[:160] if authenticated else ('Anonymous' if request else 'System'),
        actor_role=actor.role if authenticated else '',
        target_type=target._meta.model_name if target is not None else '',
        target_id=str(target.pk) if target is not None else '',
        target_label=str(target)[:200] if target is not None else '',
        animal_id_snapshot=animal_id,
        request_id=getattr(request, 'audit_request_id', '') if request else '',
        changes=changes or {},
    )


def cleanup_audit_events(*, due_only=False):
    now = timezone.now()
    last = AuditEvent.objects.filter(action='audit.retention.pruned').first()
    if due_only and last and last.created_at > now - timedelta(minutes=settings.AUDIT_CLEANUP_INTERVAL_MINUTES): return None
    counts = {}
    with transaction.atomic():
        for category, days in settings.AUDIT_RETENTION_DAYS.items():
            cutoff = now - timedelta(days=days)
            query = AuditEvent.objects.filter(category=category, created_at__lt=cutoff)
            removed = 0
            while True:
                ids = list(query.values_list('pk', flat=True)[:1000])
                if not ids: break
                removed += AuditEvent.objects.filter(pk__in=ids).delete()[0]
            counts[category] = {'removed': removed, 'before': cutoff.isoformat(), 'retention_days': days}
        record('critical', 'audit.retention.pruned', changes=counts)
    return counts
