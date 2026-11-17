from django.core.management.base import BaseCommand
from shelter.audit import cleanup_audit_events


class Command(BaseCommand):
    help = 'Prune detailed audit events using the configured retention policies.'
    def add_arguments(self, parser): parser.add_argument('--due', action='store_true')
    def handle(self, *args, **options):
        result = cleanup_audit_events(due_only=options['due'])
        self.stdout.write('Audit retention cleanup: ' + ('not due' if result is None else str(result)))
