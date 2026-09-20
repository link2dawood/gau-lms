"""Public LTI endpoints.

Every route here is reached by a browser Canvas controls, before any session of
ours exists. None can be authenticated, none may trust its input, and all of
them must be renderable inside a Canvas iframe.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoOIDCLogin
from pylti1p3.exception import LtiException, OIDCException
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services import User
from apps.courses.services import get_course
from apps.lti import audit, deep_linking, keys, services, tool_conf
from apps.lti.middleware import launch_scope
from apps.lti.models import LaunchOutcome
from apps.lti.permissions import CourseScoped
from services.launch_session import establish_session, redeem_launch_ticket
from services.provisioning import provision_launch

logger = logging.getLogger(__name__)

# Where a verified launch lands. Owned by the frontend (frontend/app/launch),
# which resolves the session and routes on the role it finds.
LANDING_PATH = "/launch"

# Canvas refetches the JWKS when it meets a `kid` it does not hold, so a short
# cache is safe: a newly generated key is picked up on the next signature that
# uses it, not after this window expires.
JWKS_CACHE_SECONDS = 300

View = Callable[..., HttpResponse]


def canvas_framable(view: View) -> View:
    """Allow Canvas to frame this page, and only Canvas.

    The platform sets `X_FRAME_OPTIONS = "DENY"`, which is right for the
    application and fatal for an LTI tool: it would blank every page in this
    module inside the Canvas iframe, including the error pages explaining why
    a launch failed. These views replace it with an explicit `frame-ancestors`
    allowlist from `CANVAS_FRAME_ANCESTORS`. Task 4.4 extends the same policy
    across the rest of the application.
    """

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        response = view(request, *args, **kwargs)
        response["Content-Security-Policy"] = tool_conf.canvas_frame_ancestors()
        return response

    return xframe_options_exempt(wrapper)


def _page(
    request: HttpRequest,
    *,
    status: int,
    title: str,
    message: str,
    details: list[tuple[str, str]] | None = None,
    hint: str | None = None,
) -> HttpResponse:
    return render(
        request,
        "lti/message.html",
        {"title": title, "message": message, "details": details, "hint": hint},
        status=status,
    )


@require_http_methods(["GET", "HEAD"])
def jwks(request: HttpRequest) -> JsonResponse:
    """Publish the tool's public keys.

    Deliberately unauthenticated, like the health endpoint, and for the same
    kind of reason: Canvas fetches this before any session exists, and it must
    be able to. Nothing here is secret — a JWKS is public by definition, and
    the document is built from public key components only (apps/lti/keys.py).
    """
    document = keys.public_jwks()
    if not document["keys"]:
        # Not an error to Canvas — an empty key set is a valid JWKS — but it
        # means every signature this tool tries to produce will fail, so it
        # must be visible to an operator rather than silent.
        logger.warning("Serving an empty JWKS: no tool keys exist. Run `manage.py create_lti_key`.")

    response = JsonResponse(document)
    response["Cache-Control"] = f"public, max-age={JWKS_CACHE_SECONDS}"
    return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
@canvas_framable
def login(request: HttpRequest) -> HttpResponse:
    """Begin the OIDC handshake for a Canvas launch.

    Canvas sends the browser here first, with the issuer and a login hint but
    no proof of anything. This endpoint generates the `state` and `nonce` that
    make the reply verifiable, stores them (apps/lti/tool_conf.py), and
    redirects the browser to Canvas's authorisation URL.

    CSRF exemption is required and safe here: the request is a genuine
    cross-site POST from Canvas, which cannot carry our CSRF token, and the
    view performs no action on anyone's behalf — it redirects, and everything
    it produces is verified on the way back.

    **Cookie check.** Rather than redirect straight to Canvas, this first
    returns a page that writes a cookie and reads it back. If that works the
    page continues automatically and the reader notices only a flicker. If the
    browser is refusing cookies to a framed third party, it offers to open the
    textbook in a new tab, where this platform is first-party and cookies are
    kept. That matters more than it sounds: the handshake itself needs a
    cookie to hold the OIDC `state`, so without the fallback a launch does not
    merely lose its session afterwards — it fails outright, and does so while
    looking like a configuration error (task 1.10, DECISIONS.md D-041).
    """
    try:
        storage = tool_conf.launch_data_storage()
        oidc = DjangoOIDCLogin(
            request,
            tool_conf.tool_conf(),
            session_service=tool_conf.session_service(request, storage),
            launch_data_storage=storage,
        )
        return oidc.enable_check_cookies(
            main_msg=(
                "Your browser is blocking the cookies this textbook needs while it is "
                "displayed inside Canvas."
            ),
            click_msg="Open the textbook in a new tab",
            loading_msg="Opening the textbook…",
        ).redirect(f"{settings.PLATFORM_BASE_URL}{reverse('lti:launch')}")
    except (OIDCException, services.PlatformNotRegistered, keys.KeyStoreError) as exc:
        logger.warning("LTI login initiation refused: %s", exc)
        return _not_configured(request)
    except Exception:
        # Same reason as the launch guard below: an exception escaping here
        # never reaches canvas_framable, and the student gets a blank frame.
        logger.exception("LTI login initiation failed unexpectedly")
        return _unavailable(request)


@csrf_exempt
@require_http_methods(["POST"])
@canvas_framable
def launch(request: HttpRequest) -> HttpResponse:
    """Accept and verify a signed launch from Canvas, then provision it.

    A thin guard around :func:`_launch`. Nothing may propagate out of this
    function: an exception escaping it would never reach `canvas_framable`,
    Django's own 500 page would be stamped `X-Frame-Options: DENY`, and the
    student would be left looking at an empty frame with nothing to report.
    """
    try:
        return _launch(request)
    except Exception as exc:
        logger.exception("LTI launch failed unexpectedly")
        audit.record_launch(outcome=LaunchOutcome.ERROR, detail=type(exc).__name__)
        return _unavailable(request)


def _launch(request: HttpRequest) -> HttpResponse:
    """Validate, then provision.

    PyLTI1p3 checks, in this order: the `state` matches the one this tool
    issued; the nonce is one we issued and has not been used (made single-use
    in apps/lti/tool_conf.py, which the library does not do); the issuer and
    audience resolve to a registration; the signature verifies against that
    platform's published keys; the deployment id is one the tool was installed
    into; and the message is a well-formed LTI message. PyJWT enforces `exp`
    while verifying the signature.
    """
    conf = tool_conf.tool_conf()
    storage = tool_conf.launch_data_storage()
    message_launch = None
    try:
        message_launch = DjangoMessageLaunch(
            request,
            conf,
            session_service=tool_conf.session_service(request, storage),
            launch_data_storage=storage,
        )
        message_launch.validate()
    except (services.PlatformNotRegistered, keys.KeyStoreError) as exc:
        logger.warning("LTI launch refused, configuration: %s", exc)
        audit.record_launch(
            outcome=LaunchOutcome.REFUSED_CONFIGURATION,
            detail=str(exc),
            **audit.claims_of(message_launch),
        )
        return _not_configured(request)
    except (LtiException, OIDCException) as exc:
        logger.warning("LTI launch refused, validation: %s", exc)
        audit.record_launch(
            outcome=LaunchOutcome.REFUSED_CONFIGURATION
            if conf.deployment_rejected
            else LaunchOutcome.REFUSED_VALIDATION,
            detail=str(exc),
            **audit.claims_of(message_launch),
        )
        if conf.deployment_rejected:
            # A registered Canvas, but not one this tool was installed into.
            # Telling this administrator the link expired would send them
            # looking in entirely the wrong place.
            return _page(
                request,
                status=400,
                title="This textbook is not installed here",
                message=(
                    "The launch came from a Canvas this tool knows, but from a place "
                    "in it where the textbook has not been installed."
                ),
                hint="Please pass this on to your Canvas administrator.",
            )
        # Otherwise reported as a category. Naming the failing check would tell
        # someone probing the endpoint which part of a forged launch to correct.
        return _page(
            request,
            status=400,
            title="This launch could not be verified",
            message=(
                "The link may have expired, or it may already have been used. "
                "Please return to Canvas and open the textbook again."
            ),
            hint="If it keeps happening, tell your instructor or your Canvas administrator.",
        )

    if message_launch.is_deep_link_launch():
        # Answered before provisioning, deliberately. A deep linking request is
        # someone building a course, and it does not always carry a course
        # context — requiring one would refuse a legitimate request at account
        # level. Nothing is created; the reply is a signed content item.
        audit.record_launch(outcome=LaunchOutcome.DEEP_LINK, **audit.claims_of(message_launch))
        return HttpResponse(deep_linking.response_form(message_launch))

    try:
        claims = services.parse_launch_claims(message_launch.get_launch_data())
        context = provision_launch(claims)
    except services.LaunchClaimsIncomplete as exc:
        # The signature was good; the contents were not enough to work with.
        # A different failure from a rejected launch, and a different fix.
        logger.warning("LTI launch verified but unusable: %s", exc)
        audit.record_launch(
            outcome=LaunchOutcome.REFUSED_CLAIMS,
            detail=str(exc),
            **audit.claims_of(message_launch),
        )
        return _page(
            request,
            status=400,
            title="Canvas did not send enough information",
            message=(
                "The launch was genuine, but it did not identify both you and the "
                "course, so the textbook cannot open."
            ),
            hint="Please tell your Canvas administrator which course this happened in.",
        )

    audit.record_launch(
        outcome=LaunchOutcome.ACCEPTED,
        issuer=claims.issuer,
        deployment_id=claims.deployment_id,
        canvas_user_id=claims.canvas_user_id,
        user_id=str(context.user.pk),
        course_id=str(context.course.pk),
        role=context.role.value,
        **{"nonce": audit.claims_of(message_launch).get("nonce", "")},
    )

    ticket = establish_session(request, context)

    # The ticket rides in the URL because the frontend has to be able to read
    # it before any of our JavaScript runs. It is single use and lives two
    # minutes, which is what makes that acceptable; the landing page removes it
    # from the address bar once redeemed, so it does not sit in history.
    query = {"lt": ticket.token}
    if claims.node_id:
        # Carried through so a deep-linked chapter opens at that chapter rather
        # than at the top of the book.
        query["node"] = claims.node_id
    landing = f"{settings.PLATFORM_BASE_URL}{LANDING_PATH}?{urlencode(query)}"
    return HttpResponseRedirect(landing)


@csrf_exempt
@require_http_methods(["POST"])
def session(request: HttpRequest) -> JsonResponse:
    """Exchange a launch ticket for a session.

    The way in for a browser that discarded the launch's session cookie because
    it was third-party. Task 1.10 opens a first-party window and calls this
    from there, where cookies are kept.

    **The ticket must arrive in the `X-Launch-Ticket` header**, and that is a
    security control, not a style choice. A cross-site HTML form can POST to
    this endpoint but cannot set a custom header, and a cross-origin fetch that
    sets one is stopped by the preflight this origin does not answer. Requiring
    the header is therefore what makes the endpoint safe against a forged
    cross-site request that would otherwise log a victim into someone else's
    launch — the reason CSRF exemption is acceptable here.
    """
    # Defence in depth behind the header requirement above. The header is the
    # control; this is the belt, and it is here because the header's protection
    # is the ABSENCE of a CORS layer — something a later change could add
    # without anything failing.
    origin = request.headers.get("Origin")
    if origin and origin != settings.PLATFORM_BASE_URL:
        logger.warning("Launch ticket redemption refused from origin %s", origin)
        return JsonResponse({"error": "forbidden_origin"}, status=403)

    ticket = request.headers.get("X-Launch-Ticket", "")
    try:
        redeemed = redeem_launch_ticket(request, ticket)
    except Exception:
        logger.exception("Redeeming a launch ticket failed unexpectedly")
        return JsonResponse({"error": "unavailable"}, status=500)

    if redeemed is None:
        # One answer for unknown, expired, already used and deactivated. Saying
        # which would tell someone guessing how close they were.
        return JsonResponse({"error": "invalid_ticket"}, status=401)

    return JsonResponse({"course_id": redeemed.course_id, "role": redeemed.role.value})


def _unavailable(request: HttpRequest) -> HttpResponse:
    """Something broke on our side. Says so, and says nothing else."""
    return _page(
        request,
        status=500,
        title="The textbook is temporarily unavailable",
        message="Something went wrong on our side while opening the textbook.",
        hint="Please try again in a few minutes. If it persists, contact your administrator.",
    )


def _not_configured(request: HttpRequest) -> HttpResponse:
    return _page(
        request,
        status=400,
        title="This textbook is not set up for your Canvas",
        message=(
            "The tool has not been registered for the Canvas instance this launch "
            "came from, so it cannot verify who you are."
        ),
        hint="Please pass this on to your Canvas administrator.",
    )


class LaunchContextView(APIView):
    """Who the reader is, and which course they are in.

    The frontend's first call after a launch (task 1.12 routes on the role it
    returns). It reports only the scope the launch established — there is no
    course parameter to pass, so there is nothing to tamper with.
    """

    permission_classes = (IsAuthenticated, CourseScoped)

    def get(self, request: Request) -> Response:
        scope = launch_scope(request)
        user = request.user
        if scope is None or not isinstance(user, User):
            # Unreachable while CourseScoped and IsAuthenticated are both in
            # permission_classes. Kept because the alternative is an assertion
            # that fails as a 500, and because a later edit to that tuple
            # should not be able to turn this into one.
            return Response({"detail": "No launch context."}, status=403)

        course = get_course(scope.course_id)
        if course is None:
            logger.warning("Launch scope names course %s, which no longer exists.", scope.course_id)
            return Response({"detail": "That course is no longer available."}, status=404)

        return Response(
            {
                "course": {
                    "id": str(course.pk),
                    "title": course.title,
                    "label": course.label,
                },
                "role": scope.role.value,
                "user": {"name": user.name, "email": user.email},
            }
        )
