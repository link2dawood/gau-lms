# syntax=docker/dockerfile:1.7
#
# Backend image — Django 5 on Python 3.12, served by Gunicorn.
# The same image runs the web process, the Celery worker and Celery beat; only
# the command differs (see docker-compose.yml).
#
# Targets:
#   base  shared runtime + system packages
#   dev   base + development dependencies, source bind-mounted by compose
#   prod  base + application source baked in, non-root, collected static

# --------------------------------------------------------------------- base
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Fail and retry rather than hang indefinitely on a slow index; an image
    # build that stalls silently is worse than one that errors.
    PIP_DEFAULT_TIMEOUT=30 \
    PIP_RETRIES=5 \
    PYTHONPATH=/app

# System packages:
#   pandoc         Word, HTML and EPUB conversion for the import pipeline
#   poppler-utils  pdftohtml and pdfimages for PDF conversion
#   libpq5         PostgreSQL client library for psycopg
#   build-essential/libpq-dev  compiling any wheel without a manylinux build
#   curl           container healthchecks
RUN apt-get update && apt-get install --no-install-recommends -y \
        pandoc \
        poppler-utils \
        libpq5 \
        libpq-dev \
        build-essential \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------- dev
FROM base AS dev

ENV DJANGO_SETTINGS_MODULE=config.settings.dev

# Dependency manifest only, so the install layer is cached until it changes.
COPY backend/pyproject.toml ./
RUN pip install ".[dev]"

# Source is bind-mounted over /app by compose; nothing is copied in.
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--reload"]

# --------------------------------------------------------------------- prod
FROM base AS prod

ENV DJANGO_SETTINGS_MODULE=config.settings.prod

COPY backend/pyproject.toml ./
RUN pip install "."

COPY backend/ /app/

# Run unprivileged. Directories the application writes to are owned by the app
# user; everything else stays read-only to it.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --home /app app \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app/staticfiles /app/media
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
