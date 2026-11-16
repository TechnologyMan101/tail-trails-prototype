import json
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .images import store_cropped_photo
from .models import AnimalHistory, AnimalPhoto, PendingPhoto, PhotoUploadBatch, Submission, SubmissionPhoto


ACTIVE_STATUSES = (PhotoUploadBatch.Status.PENDING, PhotoUploadBatch.Status.FAILED)


def _delete_pending_files(batch):
    for photo in batch.photos.all():
        if photo.original:
            photo.original.delete(save=False)


def cleanup_expired_batches(limit=None):
    ids = list(PhotoUploadBatch.objects.filter(status__in=ACTIVE_STATUSES, expires_at__lte=timezone.now()).values_list("pk", flat=True)[:limit])
    removed = 0
    for batch_id in ids:
        with transaction.atomic():
            batch = PhotoUploadBatch.objects.select_for_update().filter(pk=batch_id, status__in=ACTIVE_STATUSES, expires_at__lte=timezone.now()).first()
            if not batch:
                continue
            batch.status = PhotoUploadBatch.Status.EXPIRED
            batch.save(update_fields=["status", "updated_at"])
            _delete_pending_files(batch)
            batch.delete()
            removed += 1
    return removed


def create_photo_batch(*, user, animal, workflow, uploads, form_data=None, make_primary=False):
    cleanup_expired_batches(limit=25)
    if PhotoUploadBatch.objects.filter(user=user, status__in=ACTIVE_STATUSES).count() >= 3:
        raise ValidationError("Finish or discard an existing photo crop before starting another upload.")
    created = []
    try:
        with transaction.atomic():
            batch = PhotoUploadBatch.objects.create(
                user=user,
                animal=animal,
                workflow=workflow,
                submission_data=form_data or {},
                make_primary=make_primary,
                expires_at=timezone.now() + timedelta(minutes=max(1, settings.PHOTO_BATCH_TTL_MINUTES)),
            )
            for position, upload in enumerate(uploads):
                created.append(PendingPhoto.objects.create(
                    batch=batch,
                    original=upload,
                    original_filename=upload.name.rsplit("/", 1)[-1][:255],
                    position=position,
                ))
    except Exception:
        for photo in created:
            if photo.original:
                photo.original.delete(save=False)
        raise
    return batch


def cancel_photo_batch(batch):
    with transaction.atomic():
        locked = PhotoUploadBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.status in ACTIVE_STATUSES:
            locked.status = PhotoUploadBatch.Status.CANCELLED
            locked.save(update_fields=["status", "updated_at"])
            _delete_pending_files(locked)
            locked.delete()


def _read_pending(photo):
    photo.original.open("rb")
    try:
        return photo.original.read()
    finally:
        photo.original.close()


def finalize_photo_batch(batch_id, user, crop_payload):
    pending_files = []
    with transaction.atomic():
        batch = PhotoUploadBatch.objects.select_for_update().select_related("animal").get(pk=batch_id, user=user)
        if batch.status not in ACTIVE_STATUSES:
            raise ValidationError("This photo upload can no longer be finalized.")
        if timezone.now() >= batch.expires_at:
            raise ValidationError("This photo crop session has expired.")
        if batch.workflow == PhotoUploadBatch.Workflow.VOLUNTEER and batch.animal.is_archived:
            raise ValidationError("This animal record has been archived. Discard this upload or contact staff.")
        photos = list(batch.photos.select_for_update().order_by("position", "id"))
        if not photos:
            raise ValidationError("This upload batch contains no photos.")
        batch.status = PhotoUploadBatch.Status.FINALIZING
        batch.save(update_fields=["status", "updated_at"])

        if batch.workflow == PhotoUploadBatch.Workflow.STAFF:
            animal = type(batch.animal).objects.select_for_update().get(pk=batch.animal_id)
            official = animal.photos.order_by("position", "id")
            remove_ids = {int(value) for value in batch.submission_data.get("remove_ids", []) if str(value).isdigit()}
            valid_remove_ids = set(official.filter(pk__in=remove_ids).values_list("pk", flat=True))
            if official.exclude(pk__in=valid_remove_ids).count() + len(photos) > 5:
                batch.status = PhotoUploadBatch.Status.PENDING
                batch.save(update_fields=["status", "updated_at"])
                raise ValidationError("The gallery changed while you were cropping. Remove enough existing photos before finalizing this batch.")
            for old_photo in official.filter(pk__in=valid_remove_ids):
                for field_name in ("image", "original_image"):
                    field = getattr(old_photo, field_name, None)
                    if field: field.delete(save=False)
                old_photo.delete()
            start = animal.photos.count()
            created = []
            for offset, pending in enumerate(photos):
                values = crop_payload.get(str(pending.pk), {})
                raw = _read_pending(pending)
                created.append(store_cropped_photo(
                    AnimalPhoto(animal=animal, position=start + offset), raw, pending.original_filename,
                    crop=values.get("crop"), orientation=values.get("orientation", "landscape"),
                ))
                pending_files.append(pending)
            ordered = list(animal.photos.order_by("position", "id"))
            chosen = created[0].pk if batch.make_primary and created else batch.submission_data.get("primary_photo_id")
            if chosen and str(chosen).isdigit() and any(photo.pk == int(chosen) for photo in ordered):
                chosen = int(chosen)
                ordered.sort(key=lambda photo: photo.pk != chosen)
            for position, photo in enumerate(ordered): photo.position = position
            AnimalPhoto.objects.bulk_update(ordered, ["position"])
            AnimalHistory.objects.create(animal=animal, user=user, summary=f"Added {len(created)} cropped photo(s)")
            result = ("animal", animal.pk)
        else:
            data = batch.submission_data
            submission = Submission.objects.create(
                animal=batch.animal, user=user,
                observations=data.get("observations", ""), temperament=data.get("temperament", ""),
                good_with=data.get("good_with", ""), notes=data.get("notes", ""),
            )
            for pending in photos:
                values = crop_payload.get(str(pending.pk), {})
                raw = _read_pending(pending)
                store_cropped_photo(
                    SubmissionPhoto(submission=submission), raw, pending.original_filename,
                    crop=values.get("crop"), orientation=values.get("orientation", "landscape"),
                )
                pending_files.append(pending)
            result = ("submission", submission.pk)
        batch.status = PhotoUploadBatch.Status.COMPLETED
        batch.save(update_fields=["status", "updated_at"])

    for pending in pending_files:
        pending.original.delete(save=False)
        pending.delete()
    return result


def parse_crop_payload(post_data, photos):
    payload = {}
    for photo in photos:
        raw = post_data.get(f"crop_{photo.pk}", "{}")
        try:
            crop = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ValidationError(f"Photo {photo.position + 1} has an invalid crop area.")
        orientation = post_data.get(f"orientation_{photo.pk}", "landscape")
        if orientation not in {"landscape", "portrait"}:
            raise ValidationError(f"Photo {photo.position + 1} has an invalid orientation.")
        payload[str(photo.pk)] = {"crop": crop, "orientation": orientation}
    return payload
