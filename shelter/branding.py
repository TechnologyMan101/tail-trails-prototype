import hashlib
import io
import math

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageOps


FAVICON_SIZES = (32, 180)


def _brand_rgb(value):
    value = (value or "#245C4A").lstrip("#")
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except (TypeError, ValueError):
        return (36, 92, 74)


def _source_field(organization):
    return organization.favicon or organization.logo or None


def _cache_key(organization):
    source = _source_field(organization)
    identity = "|".join([
        str(organization.pk or 0),
        getattr(source, "name", "") or "default-heart",
        organization.primary_color or "",
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]


def _heart_icon(size, background):
    scale = size * 0.022
    points = []
    for step in range(180):
        angle = (2 * math.pi * step) / 180
        x = 16 * math.sin(angle) ** 3
        y = 13 * math.cos(angle) - 5 * math.cos(2 * angle) - 2 * math.cos(3 * angle) - math.cos(4 * angle)
        points.append((size / 2 + x * scale, size / 2 - y * scale + size * 0.04))
    image = Image.new("RGB", (size, size), background)
    ImageDraw.Draw(image).polygon(points, fill=(255, 255, 255))
    return image


def _source_icon(source, size, background):
    source.open("rb")
    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGBA")
            maximum = max(1, round(size * 0.84))
            image.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (*background, 255))
            position = ((size - image.width) // 2, (size - image.height) // 2)
            canvas.alpha_composite(image, position)
            return canvas.convert("RGB")
    finally:
        source.close()


def _render_icon(organization, size):
    background = _brand_rgb(organization.primary_color)
    source = _source_field(organization)
    if source:
        return _source_icon(source, size, background)
    return _heart_icon(size, background)


def _generated_path(organization, size, key):
    return f"branding/generated/org-{organization.pk}-{key}-{size}.png"


def _cleanup_old_variants(organization, retained_paths):
    directory = "branding/generated"
    try:
        _, files = default_storage.listdir(directory)
    except (FileNotFoundError, NotImplementedError, OSError):
        return
    prefix = f"org-{organization.pk}-"
    for filename in files:
        path = f"{directory}/{filename}"
        if filename.startswith(prefix) and path not in retained_paths:
            default_storage.delete(path)


def favicon_urls(organization, force=False):
    if not organization or not organization.pk:
        return {"favicon_32_url": "", "favicon_180_url": ""}
    key = _cache_key(organization)
    paths = {_generated_path(organization, size, key) for size in FAVICON_SIZES}
    for size in FAVICON_SIZES:
        path = _generated_path(organization, size, key)
        if force and default_storage.exists(path):
            default_storage.delete(path)
        if not default_storage.exists(path):
            image = _render_icon(organization, size)
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            default_storage.save(path, ContentFile(output.getvalue()))
    _cleanup_old_variants(organization, paths)
    return {
        "favicon_32_url": default_storage.url(_generated_path(organization, 32, key)),
        "favicon_180_url": default_storage.url(_generated_path(organization, 180, key)),
    }
