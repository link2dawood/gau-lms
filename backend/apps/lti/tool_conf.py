"""Adapter between this platform's models and PyLTI1p3.

PyLTI1p3 performs the cryptography of an LTI 1.3 handshake — building the OIDC
request, then validating the signed launch that comes back (task 1.5). It needs
three things from us, and this module supplies all three so nothing else has to
know the library's shape:

* a **tool configuration**, answering "is this issuer and client id registered,
  what are its URLs, and which key do we sign with?" — resolved through
  ``apps.lti.services``, so registrations stay the single source of truth;
* a **launch data storage** for the OIDC ``state`` and ``nonce``;
* a **session service** carrying the lifetime those entries are stored for.

State and nonce go to the ``lti_state`` cache, which is its own Redis logical
database (DECISIONS.md D-008). Flushing the page cache must not invalidate an
LTI handshake that is in flight, and a nonce is a security control: it is what
stops a captured launch being replayed.
"""

from __future__ import annotations

from django.conf import settings
from pylti1p3.contrib.django import DjangoCacheDataStorage
from pylti1p3.contrib.django.session import DjangoSessionService
from pylti1p3.deployment import Deployment
from pylti1p3.registration import Registration
from pylti1p3.tool_config.abstract import ToolConfAbstract

from apps.lti import services

# How long an in-flight handshake's state and nonce survive.
#
# PyLTI1p3 defaults to 86400 seconds. That is a 24-hour window in which a
# captured launch could be replayed, and it is far longer than the handshake
# needs: the library's own state cookie expires in 5 minutes. Ten minutes
# leaves room for a slow redirect chain and closes the window the rest of the
# way.
LAUNCH_DATA_TTL_SECONDS = 600


class PlatformToolConf(ToolConfAbstract):  # type: ignore[misc]
    """Tool configuration backed by registered platforms rather than a JSON file.

    PyLTI1p3 ships a file-based configuration. Ours reads the database, so
    adding a Canvas instance is a `sync_lti_platforms` run rather than a
    redeploy, and an inactive registration stops launching immediately.
    """

    def __init__(self) -> None:
        super().__init__()
        # Set when a launch names a registered platform but a deployment the
        # tool was never installed into. The library reports every validation
        # failure as one undifferentiated exception, and this is the one case
        # where the administrator's fix is completely different from "the link
        # expired" — so the view needs to be able to tell them apart. One
        # instance per request, so there is no state to leak between launches.
        self.deployment_rejected = False
        # PyLTI1p3 assumes one client per issuer unless told otherwise, and on
        # that assumption it resolves a launch by issuer alone and ignores the
        # client id the launch carries. Where an institution really does have
        # two developer keys on one Canvas, that would validate the launch
        # against whichever registration happened to be found first. Declaring
        # the multi-client issuers makes the library ask for the client id.
        #
        # One query per handshake. Correct beats cached here: a registration
        # added between requests must take effect on the next launch.
        for issuer in services.issuers_with_multiple_registrations():
            self.set_iss_has_many_clients(issuer)

    def find_registration_by_issuer(
        self, iss: str, *args: object, **kwargs: object
    ) -> Registration:
        return self._registration(self._sole_registration(iss))

    def find_registration_by_params(
        self, iss: str, client_id: str, *args: object, **kwargs: object
    ) -> Registration:
        return self._registration(services.get_platform(iss, client_id))

    def find_deployment(self, iss: str, deployment_id: str) -> Deployment | None:
        return self._deployment(iss, deployment_id, client_id=None)

    def find_deployment_by_params(
        self, iss: str, deployment_id: str, client_id: str, *args: object, **kwargs: object
    ) -> Deployment | None:
        return self._deployment(iss, deployment_id, client_id)

    def _deployment(self, iss: str, deployment_id: str, client_id: str | None) -> Deployment | None:
        """Confirm the tool was actually installed into this deployment.

        Returning None makes PyLTI1p3 reject the launch. A valid signature for
        a deployment this tool was never installed into is still not a launch
        this tool serves. Deliberately does not build a Registration: that
        reads a private key from disk, which an existence check has no business
        doing.
        """
        try:
            platform = (
                self._sole_registration(iss)
                if client_id is None
                else services.get_platform(iss, client_id)
            )
        except services.PlatformNotRegistered:
            return None
        if not platform.accepts_deployment(deployment_id):
            self.deployment_rejected = True
            return None
        return Deployment().set_deployment_id(deployment_id)

    def _sole_registration(self, iss: str) -> services.LtiPlatform:
        """The single active registration for an issuer, or a refusal.

        Reached when a launch names no client id. If the issuer has more than
        one, there is no safe answer — choosing would mean verifying the launch
        against the wrong developer key — so it refuses rather than guesses.
        """
        candidates = services.active_platforms_for_issuer(iss)
        if len(candidates) != 1:
            raise services.PlatformNotRegistered(
                f"Issuer {iss!r} matches {len(candidates)} active registrations; "
                f"exactly one is needed to resolve a launch that carries no client id."
            )
        return candidates[0]

    def _registration(self, platform: services.LtiPlatform) -> Registration:
        # One builder, in services.py, shared with outbound service calls. Two
        # would drift, and the way they drift is silent.
        return services.registration_for(platform)


def tool_conf() -> PlatformToolConf:
    return PlatformToolConf()


class SingleUseNonceStorage(DjangoCacheDataStorage):  # type: ignore[misc]
    """Launch data storage whose nonce check consumes the nonce.

    PyLTI1p3 does not enforce single use. `MessageLaunch.validate_nonce` calls
    `check_nonce`, which reaches `CacheDataStorage.check_value`, and that is
    only ``cache.get(key) is not None`` — the entry survives. A captured launch
    could therefore be replayed for the whole lifetime of the nonce, which is
    precisely what a nonce exists to prevent, and what task 1.16 must test.

    Deleting instead of reading makes the check a consume: Redis DEL reports
    how many keys it removed, so exactly one of two concurrent replays can see
    a truthy result. There is no window between reading and deleting for the
    second to slip through.

    The nonce is consumed before the signature is checked, because that is the
    order `validate()` runs in. Someone holding a captured launch could
    therefore burn its nonce with a malformed token — but they could equally
    replay it, which is the thing being prevented, and the user simply launches
    again. Verified against pylti1p3 master, 2026-09-18.
    """

    def check_value(self, key: str) -> bool:
        return bool(self._get_cache().delete(self._prepare_key(key)))


def launch_data_storage() -> SingleUseNonceStorage:
    return SingleUseNonceStorage(cache_name=settings.LTI_STATE_CACHE_ALIAS)


def canvas_frame_ancestors() -> str:
    """The Content-Security-Policy value that lets Canvas frame our pages.

    A tool that Canvas cannot put in an iframe is not a tool. The platform-wide
    `X_FRAME_OPTIONS = "DENY"` would blank every LTI page, so the LTI views
    replace it with an explicit allowlist. Task 4.4 generalises this to the
    whole application; this is the part of it 1.5 cannot work without.

    An unset `CANVAS_FRAME_ANCESTORS` yields 'none', which denies framing
    exactly as the platform default does — no silent widening.
    """
    hosts = settings.CANVAS_FRAME_ANCESTORS
    return f"frame-ancestors {' '.join(hosts)}" if hosts else "frame-ancestors 'none'"


def session_service(
    request: object, storage: SingleUseNonceStorage | None = None
) -> DjangoSessionService:
    """Session service writing to the LTI state cache with a short lifetime.

    Order matters: the lifetime is only honoured once a storage that supports
    key expiry is installed, so the storage is set first.
    """
    service = DjangoSessionService(request)
    service.set_data_storage(storage if storage is not None else launch_data_storage())
    service.set_launch_data_lifetime(LAUNCH_DATA_TTL_SECONDS)
    return service
