#!/usr/bin/env python
"""Django command-line utility."""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImportError(
            "Django could not be imported. Is the virtual environment active, "
            "or are you running outside the backend container?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
