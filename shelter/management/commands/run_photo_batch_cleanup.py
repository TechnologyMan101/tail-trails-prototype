import time

from django.conf import settings
from django.core.management.base import BaseCommand

from shelter.photo_batches import cleanup_expired_batches
from shelter.audit import cleanup_audit_events


class Command(BaseCommand):
    help = "Run pending-photo and audit-retention cleanup at their configured intervals."

    def handle(self, *args, **options):
        interval = max(1, settings.PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES)
        self.stdout.write(f"Photo batch cleanup service ready (every {interval} minute(s))")
        next_photo = 0
        while True:
            if time.monotonic() >= next_photo:
                removed = cleanup_expired_batches()
                next_photo = time.monotonic() + interval * 60
                if removed:
                    self.stdout.write(f"Removed {removed} expired photo batch(es)")
            cleanup_audit_events(due_only=True)
            time.sleep(max(1, min(next_photo - time.monotonic(), settings.AUDIT_CLEANUP_INTERVAL_MINUTES * 60)))
