from django.conf import settings
from .branding import favicon_urls
from .models import Organization


def organization(request):
    try:
        org = Organization.current()
        return {"org": org, "app_version": settings.APP_VERSION, **favicon_urls(org)}
    except Exception:
        return {"org": None, "app_version": settings.APP_VERSION}
