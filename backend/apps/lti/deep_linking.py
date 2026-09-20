"""Answering a Canvas Deep Linking request.

Canvas sends this message when someone is building a course and wants to place
a link to tool content — a module item, an assignment, a page. The tool replies
with one or more *content items*, signed, posted back to the URL Canvas
nominated.

A content item is a link to **this tool's launch endpoint**, not to a page of
content. Canvas stores it as a resource link and launches it like any other,
which is what keeps a deep-linked chapter behind the same signature, nonce and
course checks as every other launch. Which chapter is carried as a custom
parameter, and comes back on that launch as the `custom` claim.

The foundation returns one item for the textbook as a whole. Choosing a
specific chapter needs a chapter to choose, so the picker arrives with the
content model (tasks 2.2 and 2.3); the plumbing for it — the custom parameter
and the claim that carries it back — is here and working.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.urls import reverse
from pylti1p3.contrib.django import DjangoMessageLaunch
from pylti1p3.deep_link_resource import DeepLinkResource

logger = logging.getLogger(__name__)

__all__ = ["CUSTOM_NODE_PARAM", "content_item", "response_form"]

# The custom parameter naming the content a deep link points at. Canvas echoes
# it back on the resulting launch inside the `custom` claim.
CUSTOM_NODE_PARAM = "node_id"

# What Canvas shows in its content picker for the item we return. Replaced by
# the book's own title once books exist (task 2.5).
DEFAULT_ITEM_TITLE = "Interactive Textbook"


def content_item(node_id: str = "", title: str = DEFAULT_ITEM_TITLE) -> DeepLinkResource:
    """One content item, pointing at this tool's launch endpoint.

    `iframe` rather than a new window: the reader is designed for the Canvas
    frame, and a deep-linked chapter should open where the student is already
    looking.
    """
    resource = (
        DeepLinkResource()
        .set_type("ltiResourceLink")
        .set_title(title)
        .set_url(f"{settings.PLATFORM_BASE_URL}{reverse('lti:launch')}")
        .set_target("iframe")
    )
    if node_id:
        resource.set_custom_params({CUSTOM_NODE_PARAM: node_id})
    return resource


def response_form(launch: DjangoMessageLaunch, node_id: str = "") -> str:
    """Build the self-submitting form that returns the item to Canvas.

    The response is a JWT signed with the tool's key, which is why a platform
    with no `tool_key_id` cannot answer a deep linking request at all — the
    error surfaces from the signing call, not from here.
    """
    logger.info("Answering a deep linking request%s", f" for node {node_id}" if node_id else "")
    return launch.get_deep_link().output_response_form([content_item(node_id)])
