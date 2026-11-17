FROM python:3.14.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "${APP_GID}" tailtrails \
    && useradd --uid "${APP_UID}" --gid tailtrails --create-home --shell /usr/sbin/nologin tailtrails
COPY requirements.in requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
RUN mkdir -p /app/data /app/uploads && chown -R tailtrails:tailtrails /app

USER tailtrails
EXPOSE 8000
RUN python manage.py collectstatic --noinput
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["sh", "-c", "python manage.py migrate && python manage.py cleanup_photo_batches && python manage.py reprocess_photos && python manage.py seed_demo && uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'"]

