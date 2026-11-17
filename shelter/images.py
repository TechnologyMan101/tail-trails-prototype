import io
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener


register_heif_opener()

PHOTO_ACCEPT = "image/jpeg,image/png,image/heic,image/heif,.heic,.heif"
SUPPORTED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
SUPPORTED_PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif"}


def validate_source_image(upload):
    """Reject corrupt or excessively large source images before persistence."""
    try:
        upload.seek(0)
        with Image.open(upload) as source:
            source.verify()
        upload.seek(0)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError(
            "The uploaded file is not a valid supported image."
        ) from exc


def validate_photo_upload(upload):
    """Validate an official or candidate animal-photo upload."""
    suffix = Path(str(upload.name).replace("\\", "/")).suffix.lower()
    content_type = getattr(upload, "content_type", "")
    if suffix not in SUPPORTED_PHOTO_EXTENSIONS:
        raise ValidationError(f"{upload.name} must be JPG, PNG, HEIC, or HEIF.")
    # Some browsers report HEIC/HEIF as application/octet-stream or omit the
    # media type entirely. The decoded-image check below remains authoritative.
    if (
        content_type
        and content_type not in SUPPORTED_PHOTO_CONTENT_TYPES
        and content_type != "application/octet-stream"
    ):
        raise ValidationError(f"{upload.name} must be JPG, PNG, HEIC, or HEIF.")
    validate_source_image(upload)


def store_cropped_photo(instance, raw, source_name, crop=None, orientation="landscape"):
    """Retain an uploaded source and generate an exact-ratio cropped web JPG."""
    source_suffix = Path(source_name).suffix.lower() or ".bin"
    token = uuid.uuid4().hex
    instance.original_filename = Path(source_name).name[:255]
    instance.original_image.save(
        f"{token}{source_suffix}", ContentFile(raw), save=False
    )
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened)
            if image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            ):
                rgba = image.convert("RGBA")
                background = Image.new(
                    "RGBA", rgba.size, (*settings.PHOTO_ALPHA_BACKGROUND, 255)
                )
                background.alpha_composite(rgba)
                image = background.convert("RGB")
            else:
                image = image.convert("RGB")
            width, height = settings.PHOTO_WEB_SIZE
            long_edge, short_edge = max(width, height), min(width, height)
            target = (
                (short_edge, long_edge)
                if orientation == "portrait"
                else (long_edge, short_edge)
            )
            target_ratio = target[0] / target[1]
            try:
                values = crop or {}
                x = min(1.0, max(0.0, float(values.get("x", 0))))
                y = min(1.0, max(0.0, float(values.get("y", 0))))
                selected_width = (
                    min(1.0 - x, max(0.001, float(values.get("width", 1))))
                    * image.width
                )
                selected_height = (
                    min(1.0 - y, max(0.001, float(values.get("height", 1))))
                    * image.height
                )
                left, top = x * image.width, y * image.height
                if selected_width / selected_height > target_ratio:
                    adjusted = selected_height * target_ratio
                    left += (selected_width - adjusted) / 2
                    selected_width = adjusted
                else:
                    adjusted = selected_width / target_ratio
                    top += (selected_height - adjusted) / 2
                    selected_height = adjusted
                box = tuple(
                    round(v)
                    for v in (left, top, left + selected_width, top + selected_height)
                )
                image = image.crop(box)
            except (AttributeError, TypeError, ValueError, ZeroDivisionError):
                image = ImageOps.fit(image, target, Image.Resampling.LANCZOS)
            image = image.resize(target, Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=settings.PHOTO_WEB_QUALITY,
                optimize=True,
                progressive=True,
            )
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError(
            "The uploaded file could not be cropped to a web image."
        ) from exc
    instance.image.save(f"{token}.jpg", ContentFile(output.getvalue()), save=False)
    instance.save()
    return instance


def delete_photo_files(photo):
    for field_name in ("image", "original_image"):
        field = getattr(photo, field_name, None)
        if field:
            field.delete(save=False)
