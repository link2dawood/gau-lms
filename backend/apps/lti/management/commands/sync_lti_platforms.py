"""Write the Canvas platform configuration into the database.

Run after changing the configuration file and on every deployment. It is
idempotent, so running it when nothing has changed is free and safe.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.lti import services


class Command(BaseCommand):
    help = (
        "Register or update the Canvas platforms listed in the JSON file named by "
        "LTI_PLATFORMS_FILE. Never deletes a registration; registrations the file "
        "does not mention are reported instead."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--file",
            default=None,
            help="Path to the configuration file. Defaults to LTI_PLATFORMS_FILE.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change and roll back without writing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            registrations = services.load_registrations(options["file"])
            report = services.sync_platforms(registrations, dry_run=options["dry_run"])
        except services.RegistrationSourceError as exc:
            # A configuration fault, not a bug: report it as a failed command
            # rather than a traceback, so a deployment stops on a clear message.
            raise CommandError(str(exc)) from exc

        for label, entries in (
            ("registered", report.created),
            ("updated", report.updated),
            ("unchanged", report.unchanged),
        ):
            for entry in entries:
                self.stdout.write(f"  {label:<10} {entry}")

        for entry in report.unmanaged:
            self.stdout.write(
                self.style.WARNING(
                    f"  in database but not in the configuration, left untouched: {entry}"
                )
            )

        summary = (
            f"{len(report.created)} registered, {len(report.updated)} updated, "
            f"{len(report.unchanged)} unchanged, {len(report.unmanaged)} unmanaged"
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry run, nothing written: {summary}"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
