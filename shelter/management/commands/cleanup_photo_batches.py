from django.core.management.base import BaseCommand

from shelter.photo_batches import cleanup_expired_batches


class Command(BaseCommand):
    help = "Delete expired, unfinished animal-photo upload batches and their private files."

    def handle(self, *args, **options):
        removed = cleanup_expired_batches()
        self.stdout.write(
            f"Photo batch cleanup complete ({removed} expired batch(es) removed)"
        )
