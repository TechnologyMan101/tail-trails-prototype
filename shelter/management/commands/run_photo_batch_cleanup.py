import time

from django.conf import settings
from django.core.management.base import BaseCommand

from shelter.photo_batches import cleanup_expired_batches


class Command(BaseCommand):
    help = "Run expired photo-batch cleanup at the configured interval."

    def handle(self, *args, **options):
        interval = max(1, settings.PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES)
        self.stdout.write(
            f"Photo batch cleanup service ready (every {interval} minute(s))"
        )
        while True:
            removed = cleanup_expired_batches()
            if removed:
                self.stdout.write(f"Removed {removed} expired photo batch(es)")
            time.sleep(interval * 60)
