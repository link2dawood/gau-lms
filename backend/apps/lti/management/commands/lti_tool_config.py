"""Emit the JSON a Canvas administrator pastes when creating the developer key.

Generated rather than written down, because every URL in it is derived from
`PLATFORM_BASE_URL`. A configuration copied from documentation is a
configuration that silently points at staging after someone forgets to change
one line — and the symptom is a launch that fails validation for no visible
reason.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.urls import reverse

# Canvas's own identifier for its LTI extension block. A protocol constant
# defined by the platform's schema, not this institution's configuration.
CANVAS_PLATFORM = "canvas.instructure.com"

# The only service this tool asks for in Phase 1. Names and Roles is what the
# roster sync reads (task 1.13). No grade scopes: the platform does not
# assess, and a scope requested but unused is a permission granted for nothing.
SCOPES = ["https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly"]

TITLE = "Interactive Textbook"
DESCRIPTION = "Read the course textbook as structured, searchable web content."


class Command(BaseCommand):
    help = (
        "Print the LTI 1.3 tool configuration JSON for a Canvas developer key. "
        "Every URL is built from PLATFORM_BASE_URL."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--privacy-level",
            choices=["public", "name_only", "email_only", "anonymous"],
            default="public",
            help=(
                "How much Canvas tells the tool about a person. 'public' sends name and "
                "email; 'anonymous' sends neither, and the reader then has no name. "
                "GAU's decision, not a technical one."
            ),
        )
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args: Any, **options: Any) -> None:
        base = settings.PLATFORM_BASE_URL
        host = urlparse(base).hostname or ""

        if not base.startswith("https://"):
            # Not fatal: a developer generating this against localhost is doing
            # the right thing. Fatal in the sense that Canvas will refuse it.
            self.stderr.write(
                self.style.WARNING(
                    f"PLATFORM_BASE_URL is {base!r}. Canvas requires https for a real "
                    f"developer key — this output is only usable for local testing."
                )
            )

        config = {
            "title": TITLE,
            "description": DESCRIPTION,
            "oidc_initiation_url": f"{base}{reverse('lti:login')}",
            "target_link_uri": f"{base}{reverse('lti:launch')}",
            "public_jwk_url": f"{base}{reverse('lti:jwks')}",
            "scopes": SCOPES,
            "extensions": [
                {
                    "platform": CANVAS_PLATFORM,
                    "domain": host,
                    "privacy_level": options["privacy_level"],
                    "settings": {
                        "placements": [
                            {
                                "placement": "course_navigation",
                                "message_type": "LtiResourceLinkRequest",
                                "text": TITLE,
                                "enabled": True,
                                "default": "enabled",
                                "windowTarget": "_self",
                            },
                            {
                                "placement": "link_selection",
                                "message_type": "LtiDeepLinkingRequest",
                                "text": TITLE,
                                "enabled": True,
                            },
                            {
                                "placement": "assignment_selection",
                                "message_type": "LtiDeepLinkingRequest",
                                "text": TITLE,
                                "enabled": True,
                            },
                        ],
                    },
                }
            ],
        }

        self.stdout.write(json.dumps(config, indent=options["indent"]))
