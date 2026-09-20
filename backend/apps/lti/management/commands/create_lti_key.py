"""Generate an RSA keypair for this tool.

Run once when the platform is first set up, and again for each rotation. The
command only creates the key; pointing a Canvas registration at it is a
separate, deliberate step through the platform configuration file, so a
rotation is never a side effect of generating a key.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.lti import keys


class Command(BaseCommand):
    help = (
        "Generate an RSA keypair for signing requests to Canvas and print its kid. "
        "Existing keys are never touched; every key in LTI_TOOL_KEY_DIR stays "
        "published at /lti/jwks/ until its file is deleted."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            key = keys.generate_key()
        except keys.KeyStoreError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Created tool key {key.kid}"))
        self.stdout.write(f"  private key : {key.path}  (never commit or copy this)")
        self.stdout.write(f"  published at: {settings.PLATFORM_BASE_URL}/lti/jwks/")
        self.stdout.write(
            "\nTo sign with it, set this platform's tool_key_id in the file named by "
            f'LTI_PLATFORMS_FILE:\n\n    "tool_key_id": "{key.kid}"\n\n'
            "then run `manage.py sync_lti_platforms`."
        )
