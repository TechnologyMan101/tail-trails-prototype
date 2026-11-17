import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    x.strip()
    for x in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if x.strip()
]
CSRF_TRUSTED_ORIGINS = [
    x.strip() for x in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "shelter",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shelter.context.organization",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("DB_ENGINE", "postgres") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("DATABASE_PATH", BASE_DIR / "data" / "tailtrails.db"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "tailtrails"),
            "USER": os.getenv("POSTGRES_USER", "tailtrails"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "tailtrails"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_USER_MODEL = "shelter.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "America/Los_Angeles")
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.getenv("UPLOAD_FOLDER", BASE_DIR / "uploads"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "animals"
LOGOUT_REDIRECT_URL = "home"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
MAX_PHOTO_SIZE_MB = int(os.getenv("MAX_PHOTO_SIZE_MB", "25"))
MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "160"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_REQUEST_SIZE_MB * 1024 * 1024
# Files above this threshold are streamed to disk; this is not the upload limit.
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
PHOTO_WEB_SIZE = (
    int(os.getenv("PHOTO_WEB_WIDTH", "1600")),
    int(os.getenv("PHOTO_WEB_HEIGHT", "1200")),
)
PHOTO_WEB_QUALITY = int(os.getenv("PHOTO_WEB_QUALITY", "82"))
PHOTO_ALPHA_BACKGROUND = (238, 242, 239)
BRANDING_LOGO_SIZE = int(os.getenv("BRANDING_LOGO_SIZE", "512"))
BRANDING_BANNER_SIZE = (
    int(os.getenv("BRANDING_BANNER_WIDTH", "1920")),
    int(os.getenv("BRANDING_BANNER_HEIGHT", "640")),
)
BRANDING_WEB_QUALITY = int(os.getenv("BRANDING_WEB_QUALITY", "85"))
BRANDING_MAX_SIZE_MB = int(os.getenv("BRANDING_MAX_SIZE_MB", "25"))
PHOTO_BATCH_TTL_MINUTES = int(os.getenv("PHOTO_BATCH_TTL_MINUTES", "30"))
PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES = int(
    os.getenv("PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES", "60")
)
