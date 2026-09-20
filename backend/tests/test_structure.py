"""Tests that protect the agreed project layout.

Structure rules that are only written down get broken quietly. These assert the
ones whose breach is silent rather than loud — a missing migration mapping does
not raise anything, it just means an app's tables are never created.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

BACKEND_ROOT = Path(settings.BASE_DIR)


def local_app_labels() -> list[str]:
    return [app.split(".")[-1] for app in settings.INSTALLED_APPS if app.startswith("apps.")]


class TestMigrationsAreCentralised:
    def test_every_local_app_is_mapped(self) -> None:
        """An app missing from MIGRATION_MODULES is treated by Django as having
        no migrations at all: `migrate` succeeds and creates nothing."""
        for label in local_app_labels():
            assert label in settings.MIGRATION_MODULES, (
                f"apps.{label} has no MIGRATION_MODULES entry, so Django will not "
                f"find its migrations and its tables will never be created."
            )

    def test_every_mapping_points_at_a_real_package(self) -> None:
        for label, module in settings.MIGRATION_MODULES.items():
            package = BACKEND_ROOT.joinpath(*module.split("."))
            assert (package / "__init__.py").exists(), (
                f"MIGRATION_MODULES maps {label} to {module}, which is not a package."
            )

    def test_no_app_keeps_its_own_migrations_directory(self) -> None:
        """A stray per-app migrations/ folder silently wins over the central one."""
        strays = [p for p in (BACKEND_ROOT / "apps").glob("*/migrations") if p.is_dir()]
        assert strays == [], f"Migrations must live in backend/migrations/: found {strays}"


class TestModuleBoundaries:
    def test_apps_are_directories_not_single_files(self) -> None:
        """Each module is its own directory (rule C.1 and the agreed layout)."""
        for label in local_app_labels():
            assert (BACKEND_ROOT / "apps" / label).is_dir()
