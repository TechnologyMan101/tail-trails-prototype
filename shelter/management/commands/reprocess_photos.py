from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from shelter.images import store_photo_upload
from shelter.models import AnimalPhoto, SubmissionPhoto


class Command(BaseCommand):
    help = "Backfill retained originals and optimized JPGs for photos uploaded before the dual-file pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Regenerate every local web image from its retained original using the current orientation and background settings.",
        )

    def handle(self, *args, **options):
        converted = 0
        for model in (AnimalPhoto, SubmissionPhoto):
            if options["all"]:
                for photo in model.objects.exclude(original_image="").iterator():
                    old_image_name = photo.image.name
                    old_original_name = photo.original_image.name
                    image_storage = photo.image.storage
                    original_storage = photo.original_image.storage
                    photo.original_image.open("rb")
                    source = File(photo.original_image.file, name=Path(old_original_name).name)
                    store_photo_upload(photo, source)
                    if old_image_name and old_image_name != photo.image.name:
                        image_storage.delete(old_image_name)
                    if old_original_name and old_original_name != photo.original_image.name:
                        original_storage.delete(old_original_name)
                    converted += 1
                continue
            for photo in model.objects.exclude(image="").filter(original_image="").iterator():
                old_name = photo.image.name
                storage = photo.image.storage
                photo.image.open("rb")
                source = File(photo.image.file, name=Path(old_name).name)
                store_photo_upload(photo, source)
                if old_name and old_name != photo.image.name:
                    storage.delete(old_name)
                converted += 1
        label = "photo(s) regenerated" if options["all"] else "legacy photo(s) converted"
        self.stdout.write(self.style.SUCCESS(f"Photo optimization ready ({converted} {label})"))

