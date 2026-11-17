import os
import platform
import shutil
import time
from pathlib import Path

import django
from django.conf import settings
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


def format_bytes(value):
    if value is None:
        return "Unavailable"
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(amount) < 1024 or unit == "PiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024


def format_duration(seconds):
    if seconds is None:
        return "Unavailable"
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _nearest_existing_path(path):
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def storage_snapshot():
    configured = Path(settings.MEDIA_ROOT)
    measured = _nearest_existing_path(configured)
    try:
        usage = shutil.disk_usage(measured)
        percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0
        return {
            "configured_path": str(configured),
            "measured_path": str(measured),
            "total": format_bytes(usage.total),
            "used": format_bytes(usage.used),
            "free": format_bytes(usage.free),
            "percent": percent,
            "available": True,
        }
    except OSError as exc:
        return {
            "configured_path": str(configured),
            "measured_path": str(measured),
            "total": "Unavailable",
            "used": "Unavailable",
            "free": "Unavailable",
            "percent": 0,
            "available": False,
            "error": str(exc),
        }


def database_snapshot():
    started = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        latency_ms = round((time.monotonic() - started) * 1000, 1)
        status = "Connected"
        error = ""
    except Exception as exc:
        latency_ms = None
        status = "Unavailable"
        error = str(exc)
    try:
        latest = MigrationRecorder.Migration.objects.order_by("-applied").first()
        migration = (
            f"{latest.app}.{latest.name}" if latest else "No migrations recorded"
        )
        migration_time = latest.applied if latest else None
    except Exception:
        migration = "Unavailable"
        migration_time = None
    return {
        "status": status,
        "healthy": status == "Connected",
        "engine": connection.vendor,
        "latency_ms": latency_ms,
        "latest_migration": migration,
        "latest_migration_time": migration_time,
        "error": error,
    }


def _read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return ""


def _proc_memory():
    values = {}
    for line in _read_text("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        pieces = raw.strip().split()
        if pieces and pieces[0].isdigit():
            values[key] = int(pieces[0]) * 1024
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used = total - available if total is not None and available is not None else None
    return total, used, available, "Kernel-visible memory"


def _proc_swap():
    values = {}
    for line in _read_text("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        pieces = raw.strip().split()
        if pieces and pieces[0].isdigit():
            values[key] = int(pieces[0]) * 1024
    total = values.get("SwapTotal")
    available = values.get("SwapFree")
    used = total - available if total is not None and available is not None else None
    return total, used, available, "Kernel-visible swap"


def _memory_snapshot():
    current_text = _read_text("/sys/fs/cgroup/memory.current")
    maximum_text = _read_text("/sys/fs/cgroup/memory.max")
    if current_text.isdigit() and maximum_text.isdigit():
        used = int(current_text)
        total = int(maximum_text)
        available = max(0, total - used)
        source = "Container cgroup"
    else:
        total, used, available, source = _proc_memory()
    percent = round((used / total) * 100, 1) if used is not None and total else 0
    return {
        "source": source,
        "total": format_bytes(total),
        "used": format_bytes(used),
        "available": format_bytes(available),
        "percent": percent,
    }


def _swap_snapshot():
    current_text = _read_text("/sys/fs/cgroup/memory.swap.current")
    maximum_text = _read_text("/sys/fs/cgroup/memory.swap.max")
    if current_text.isdigit() and maximum_text.isdigit():
        used = int(current_text)
        total = int(maximum_text)
        available = max(0, total - used)
        source = "Container cgroup"
    else:
        total, used, available, source = _proc_swap()
    percent = round((used / total) * 100, 1) if used is not None and total else 0
    return {
        "source": source,
        "total": format_bytes(total),
        "used": format_bytes(used),
        "available": format_bytes(available),
        "percent": percent,
        "enabled": bool(total),
    }


def _cpu_name():
    entries = []
    for line in _read_text("/proc/cpuinfo").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        entries.append((key.strip().lower(), value.strip()))
    for preferred in ("model name", "hardware"):
        for key, value in entries:
            if key == preferred and value:
                return value
    for key, value in entries:
        if key == "processor" and value and not value.isdigit():
            return value
    return platform.processor() or "Unavailable"


def _process_rss():
    for line in _read_text("/proc/self/status").splitlines():
        if line.startswith("VmRSS:"):
            pieces = line.split()
            if len(pieces) >= 2 and pieces[1].isdigit():
                return int(pieces[1]) * 1024
    return None


def server_snapshot():
    try:
        loads = os.getloadavg()
        load_average = " / ".join(f"{value:.2f}" for value in loads)
    except (AttributeError, OSError):
        load_average = "Unavailable"
    uptime_text = _read_text("/proc/uptime").split()
    uptime = float(uptime_text[0]) if uptime_text else None
    return {
        "operating_system": platform.platform(),
        "cpu_name": _cpu_name(),
        "python": platform.python_version(),
        "django": django.get_version(),
        "cpu_count": os.cpu_count() or "Unavailable",
        "load_average": load_average,
        "uptime": format_duration(uptime),
        "process_id": os.getpid(),
        "process_memory": format_bytes(_process_rss()),
        "memory": _memory_snapshot(),
        "swap": _swap_snapshot(),
    }


def system_snapshot():
    width, height = settings.PHOTO_WEB_SIZE
    return {
        "version": settings.APP_VERSION,
        "database": database_snapshot(),
        "storage": storage_snapshot(),
        "server": server_snapshot(),
        "images": {
            "dimensions": f"{width} x {height} (orientation-aware)",
            "quality": settings.PHOTO_WEB_QUALITY,
            "per_file_limit": f"{settings.MAX_PHOTO_SIZE_MB} MiB",
            "request_limit": f"{settings.MAX_REQUEST_SIZE_MB} MiB",
            "gallery_limit": "5 official photos",
            "crop_session": f"{settings.PHOTO_BATCH_TTL_MINUTES} minutes",
            "cleanup_interval": f"{settings.PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES} minutes",
        },
        "time_zone": settings.TIME_ZONE,
    }
