import io
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .images import validate_source_image


BRANDING_ACCEPT = {
    "logo": "image/jpeg,image/png,.jpg,.jpeg,.png",
    "favicon": "image/jpeg,image/png,.jpg,.jpeg,.png",
    "banner": "image/jpeg,image/png,image/heic,image/heif,.jpg,.jpeg,.png,.heic,.heif",
}
BRANDING_EXTENSIONS = {
    "logo": {".jpg", ".jpeg", ".png"},
    "favicon": {".jpg", ".jpeg", ".png"},
    "banner": {".jpg", ".jpeg", ".png", ".heic", ".heif"},
}
BRANDING_TYPES = {
    "logo": {"image/jpeg", "image/png"},
    "favicon": {"image/jpeg", "image/png"},
    "banner": {"image/jpeg", "image/png", "image/heic", "image/heif"},
}


def validate_branding_upload(upload, kind):
    suffix = Path(str(upload.name).replace("\\", "/")).suffix.lower()
    allowed_label = "JPG or PNG" if kind in {"logo", "favicon"} else "JPG, PNG, HEIC, or HEIF"
    if suffix not in BRANDING_EXTENSIONS[kind]:
        raise ValidationError(f"{upload.name} must be {allowed_label}.")
    content_type = getattr(upload, "content_type", "")
    if content_type and content_type not in BRANDING_TYPES[kind] and content_type != "application/octet-stream":
        raise ValidationError(f"{upload.name} must be {allowed_label}.")
    if upload.size > settings.BRANDING_MAX_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"{upload.name} is larger than {settings.BRANDING_MAX_SIZE_MB} MiB.")
    validate_source_image(upload)


def _source_bytes(field):
    field.open("rb")
    try:
        return field.read()
    finally:
        field.close()


def _target_size(kind):
    if kind == "banner":
        return settings.BRANDING_BANNER_SIZE
    return (settings.BRANDING_LOGO_SIZE, settings.BRANDING_LOGO_SIZE)


def _crop_box(image, crop, target_size):
    target_ratio = target_size[0] / target_size[1]
    try:
        x = min(1.0, max(0.0, float(crop.get("x", 0))))
        y = min(1.0, max(0.0, float(crop.get("y", 0))))
        width = min(1.0 - x, max(0.001, float(crop.get("width", 1))))
        height = min(1.0 - y, max(0.001, float(crop.get("height", 1))))
        left, top = x * image.width, y * image.height
        right, bottom = (x + width) * image.width, (y + height) * image.height
    except (AttributeError, TypeError, ValueError):
        left, top, right, bottom = 0, 0, image.width, image.height

    selected_width, selected_height = right - left, bottom - top
    selected_ratio = selected_width / selected_height
    if selected_ratio > target_ratio:
        adjusted_width = selected_height * target_ratio
        left += (selected_width - adjusted_width) / 2
        right = left + adjusted_width
    else:
        adjusted_height = selected_width / target_ratio
        top += (selected_height - adjusted_height) / 2
        bottom = top + adjusted_height
    return tuple(round(value) for value in (left, top, right, bottom))


def _render(raw, kind, crop):
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened)
            target = _target_size(kind)
            image = image.crop(_crop_box(image, crop, target))
            image = image.resize(target, Image.Resampling.LANCZOS)
            output = io.BytesIO()
            if kind == "banner":
                if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                    rgba = image.convert("RGBA")
                    canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                    canvas.alpha_composite(rgba)
                    image = canvas.convert("RGB")
                else:
                    image = image.convert("RGB")
                image.save(output, format="JPEG", quality=settings.BRANDING_WEB_QUALITY, optimize=True, progressive=True)
                return output.getvalue(), ".jpg"
            image = image.convert("RGBA")
            image.save(output, format="PNG", optimize=True)
            return output.getvalue(), ".png"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("The branding image could not be processed.") from exc


def branding_preview_bytes(raw):
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGBA")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            background = Image.new("RGBA", image.size, (245, 247, 246, 255))
            background.alpha_composite(image)
            output = io.BytesIO()
            background.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("The branding image could not be previewed.") from exc


def process_branding_asset(organization, kind, upload=None, crop=None):
    original_field = getattr(organization, f"{kind}_original")
    if upload:
        upload.seek(0)
        raw = upload.read()
        source_name = Path(str(upload.name).replace("\\", "/")).name
    elif original_field:
        raw = _source_bytes(original_field)
        source_name = getattr(organization, f"{kind}_original_filename") or Path(original_field.name).name
    else:
        return False

    crop = crop or {}
    rendered, suffix = _render(raw, kind, crop)
    old_web_name = getattr(organization, kind).name
    old_original_name = original_field.name

    if upload:
        source_suffix = Path(source_name).suffix.lower() or ".bin"
        original_field.save(f"{uuid.uuid4().hex}{source_suffix}", ContentFile(raw), save=False)
        setattr(organization, f"{kind}_original_filename", source_name[:255])
    getattr(organization, kind).save(f"{uuid.uuid4().hex}{suffix}", ContentFile(rendered), save=False)
    setattr(organization, f"{kind}_crop", crop)
    organization.save(update_fields=[
        kind, f"{kind}_original", f"{kind}_original_filename", f"{kind}_crop",
    ])

    current_web_name = getattr(organization, kind).name
    current_original_name = getattr(organization, f"{kind}_original").name
    storage = getattr(organization, kind).storage
    if old_web_name and old_web_name not in {current_web_name, current_original_name}:
        storage.delete(old_web_name)
    if upload and old_original_name and old_original_name not in {current_original_name, current_web_name}:
        original_field.storage.delete(old_original_name)
    return True


def delete_branding_asset(organization, kind):
    web = getattr(organization, kind)
    original = getattr(organization, f"{kind}_original")
    files = [(field.name, field.storage) for field in (web, original) if field and field.name]
    setattr(organization, kind, "")
    setattr(organization, f"{kind}_original", "")
    setattr(organization, f"{kind}_original_filename", "")
    setattr(organization, f"{kind}_crop", {})
    organization.save(update_fields=[kind, f"{kind}_original", f"{kind}_original_filename", f"{kind}_crop"])
    deleted = set()
    for name, storage in files:
        if name not in deleted:
            storage.delete(name)
            deleted.add(name)
