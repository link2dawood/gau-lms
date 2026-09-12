"""GAU Interactive Textbook Platform — Django project configuration."""

from __future__ import annotations

# Importing the Celery app here means `celery -A config.celery` and any Django
# process share one configured app instance, so a task registered at import
# time is visible to both.
from config.celery import app as celery_app

__all__ = ["celery_app"]
