"""Platform registrations, tool keys, and the single-use nonce.

The nonce test is the "replayed nonce" case from task 1.16. It sits at the
storage layer because that is where single use is implemented — PyLTI1p3's own
check only reads the key and leaves it in place (D-030).
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest

from apps.lti import keys, tool_conf
from apps.lti.models import LtiPlatform
from apps.lti.services import (
    PlatformNotRegistered,
    RegistrationSourceError,
    active_platforms_for_issuer,
    get_platform,
    issuers_with_multiple_registrations,
    load_registrations,
    sync_platforms,
)
from tests.factories import DEPLOYMENT_ID, ISSUER, LtiPlatformFactory

pytestmark = pytest.mark.django_db


def registration(**overrides: Any) -> dict[str, Any]:
    entry = {
        "issuer": ISSUER,
        "client_id": "10000000000123",
        "deployment_ids": [DEPLOYMENT_ID],
        "auth_login_url": "https://canvas.test/api/lti/authorize_redirect",
        "auth_token_url": "https://canvas.test/login/oauth2/token",
        "jwks_url": "https://canvas.test/api/lti/security/jwks",
    }
    entry.update(overrides)
    return entry


class TestRegisteringPlatforms:
    def test_a_first_sync_registers(self) -> None:
        report = sync_platforms([registration()])
        assert len(report.created) == 1
        assert LtiPlatform.objects.count() == 1

    def test_syncing_the_same_file_twice_changes_nothing(self) -> None:
        sync_platforms([registration()])
        report = sync_platforms([registration()])
        assert (len(report.created), len(report.updated), len(report.unchanged)) == (0, 0, 1)

    def test_an_omitted_optional_key_resets_rather_than_lingers(self) -> None:
        """The file is the source of truth. Dropping "is_active": false must
        re-enable the platform, or a disabled registration could never be
        re-enabled by editing the file."""
        sync_platforms([registration(is_active=False)])
        sync_platforms([registration()])
        assert LtiPlatform.objects.get().is_active is True

    def test_a_sync_never_deletes(self) -> None:
        """Removing a row would end every launch from that platform, silently."""
        LtiPlatformFactory(client_id="99999")
        report = sync_platforms([registration()])
        assert len(report.unmanaged) == 1
        assert LtiPlatform.objects.count() == 2

    def test_an_empty_list_is_refused(self) -> None:
        """An empty file and a wrongly mounted one are indistinguishable."""
        with pytest.raises(RegistrationSourceError):
            sync_platforms([])

    @pytest.mark.parametrize(
        "bad",
        [
            {"issuer": None},
            {"issuer": 0},
            {"client_id": ""},
            {"deployment_ids": "not-a-list"},
            {"is_active": "yes"},
            {"tool_key_id": 7},
            {"unexpected": "typo"},
        ],
    )
    def test_a_malformed_entry_is_refused_before_it_is_stored(self, bad: dict[str, Any]) -> None:
        with pytest.raises(RegistrationSourceError):
            sync_platforms([registration(**bad)])
        assert LtiPlatform.objects.count() == 0

    def test_a_dry_run_writes_nothing(self) -> None:
        sync_platforms([registration()], dry_run=True)
        assert LtiPlatform.objects.count() == 0

    def test_a_file_is_read_and_validated(self, tmp_path: Path) -> None:
        source = tmp_path / "platforms.json"
        source.write_text(json.dumps([registration()]))
        assert load_registrations(source)[0]["issuer"] == ISSUER

    def test_a_file_that_is_not_a_list_is_refused(self, tmp_path: Path) -> None:
        source = tmp_path / "platforms.json"
        source.write_text(json.dumps(registration()))
        with pytest.raises(RegistrationSourceError):
            load_registrations(source)


class TestResolvingAPlatform:
    def test_an_unregistered_issuer_is_refused(self) -> None:
        with pytest.raises(PlatformNotRegistered):
            get_platform("https://elsewhere.test", "1")

    def test_a_retired_registration_is_invisible(self) -> None:
        """Inactive is filtered here rather than by the caller, so a code path
        that forgets to check cannot accept a superseded developer key."""
        LtiPlatformFactory(client_id="1", is_active=False)
        with pytest.raises(PlatformNotRegistered):
            get_platform(ISSUER, "1")
        assert active_platforms_for_issuer(ISSUER) == []

    def test_an_issuer_with_two_keys_is_reported_as_multi_client(self) -> None:
        """Without this PyLTI1p3 resolves by issuer alone and ignores the
        client id, verifying a launch against whichever key it finds first."""
        LtiPlatformFactory(client_id="1")
        assert issuers_with_multiple_registrations() == []
        LtiPlatformFactory(client_id="2")
        assert issuers_with_multiple_registrations() == [ISSUER]

    def test_a_wrong_audience_does_not_resolve(self) -> None:
        """The `aud` claim becomes the client id. A launch carrying someone
        else's is not a launch this tool serves."""
        LtiPlatformFactory(client_id="10000000000123")
        with pytest.raises(PlatformNotRegistered):
            get_platform(ISSUER, "10000000000999")

    def test_a_deployment_the_tool_was_not_installed_into_is_refused(self) -> None:
        platform = LtiPlatformFactory(client_id="1")
        assert platform.accepts_deployment(DEPLOYMENT_ID) is True
        assert platform.accepts_deployment("99:other") is False

    def test_a_registration_with_no_deployments_accepts_none(self) -> None:
        """Canvas issues a deployment id only once the tool is installed, so a
        platform can legitimately be registered with none — and must then
        launch nothing."""
        platform = LtiPlatformFactory(client_id="1", deployment_ids=[])
        assert platform.accepts_deployment(DEPLOYMENT_ID) is False


class TestToolKeys:
    @pytest.fixture(autouse=True)
    def _key_dir(self, settings: Any, tmp_path: Path) -> None:
        settings.LTI_TOOL_KEY_DIR = tmp_path / "lti-keys"

    def test_a_generated_key_is_readable_only_by_its_owner(self) -> None:
        key = keys.generate_key()
        assert stat.S_IMODE(key.path.stat().st_mode) == 0o600

    def test_the_key_id_is_the_key_thumbprint(self) -> None:
        """Derived from the key material, so our JWKS and the library that
        signs with it arrive at the same value independently (D-027)."""
        key = keys.generate_key()
        published = keys.public_jwks()["keys"]
        assert [jwk["kid"] for jwk in published] == [key.kid]

    def test_the_published_document_carries_no_private_component(self) -> None:
        keys.generate_key()
        for jwk in keys.public_jwks()["keys"]:
            assert set(jwk) == {"kty", "use", "alg", "kid", "n", "e"}

    def test_an_absent_key_directory_serves_a_valid_empty_document(self) -> None:
        """Canvas fetches this on its way to trusting the tool. Failing the
        request can break installation; an empty key set cannot."""
        assert keys.public_jwks() == {"keys": []}

    def test_an_unreadable_key_does_not_take_the_others_down(self) -> None:
        good = keys.generate_key()
        (keys.key_directory() / "broken.pem").write_text("not a key")
        assert [jwk["kid"] for jwk in keys.public_jwks()["keys"]] == [good.kid]

    def test_asking_for_a_key_that_does_not_exist_is_an_error_not_a_crash(self) -> None:
        with pytest.raises(keys.KeyStoreError):
            keys.private_key_pem("nope")

    def test_both_halves_of_a_key_are_retrievable(self) -> None:
        key = keys.generate_key()
        assert "PRIVATE KEY" in keys.private_key_pem(key.kid)
        assert "PUBLIC KEY" in keys.public_key_pem(key.kid)


class TestTheNonceIsSingleUse:
    """The replayed-launch case. PyLTI1p3 only reads the nonce and leaves it in
    place, so without this a captured launch is replayable for its lifetime.
    """

    def test_a_nonce_is_accepted_once_and_then_refused(self) -> None:
        storage = tool_conf.launch_data_storage()
        storage.set_value("lti1p3-nonce-abc", True, 600)

        assert storage.check_value("lti1p3-nonce-abc") is True
        assert storage.check_value("lti1p3-nonce-abc") is False

    def test_a_nonce_that_was_never_issued_is_refused(self) -> None:
        assert tool_conf.launch_data_storage().check_value("lti1p3-nonce-never") is False
