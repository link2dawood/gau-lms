"""Tests for the environment reader.

Every setting the platform has passes through this module, so a silent
misparse here becomes a security or availability problem somewhere else —
``DEBUG`` on in production, an unset host list accepted, a database URL
pointing somewhere unintended. The behaviour worth pinning down is what happens
to *bad* input, not what happens to good input.
"""

from __future__ import annotations

import pytest

from core.settings.env import (
    ImproperlyConfigured,
    get_bool,
    get_int,
    get_list,
    get_str,
    parse_database_url,
    parse_redis_url,
    require_str,
)


class TestGetBool:
    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "True", "yes", "on", " true "])
    def test_accepts_the_usual_spellings_of_true(
        self, raw: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROBE", raw)
        assert get_bool("PROBE", default=False) is True

    @pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off"])
    def test_accepts_the_usual_spellings_of_false(
        self, raw: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROBE", raw)
        assert get_bool("PROBE", default=True) is False

    def test_unset_yields_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PROBE", raising=False)
        assert get_bool("PROBE", default=True) is True

    def test_empty_is_treated_as_unset_not_as_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Consistent with get_str and get_list.

        An empty value means "I did not configure this", which is not the same
        statement as "I configured this to be off".
        """
        monkeypatch.setenv("PROBE", "")
        assert get_bool("PROBE", default=True) is True

    def test_a_typo_is_an_error_not_a_silent_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The whole point of the module.

        DJANGO_DEBUG=Ture must not quietly ship a production setting that looks
        as though it was configured.
        """
        monkeypatch.setenv("PROBE", "Ture")
        with pytest.raises(ImproperlyConfigured, match="is not a boolean"):
            get_bool("PROBE", default=False)


class TestRequiredAndOptional:
    def test_a_missing_required_variable_names_itself(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PROBE", raising=False)
        with pytest.raises(ImproperlyConfigured, match="PROBE"):
            require_str("PROBE")

    def test_an_empty_required_variable_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROBE", "   ")
        with pytest.raises(ImproperlyConfigured, match="PROBE"):
            require_str("PROBE")

    def test_optional_falls_back_to_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PROBE", raising=False)
        assert get_str("PROBE", "fallback") == "fallback"

    def test_a_non_numeric_integer_is_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROBE", "sixty")
        with pytest.raises(ImproperlyConfigured, match="is not an integer"):
            get_int("PROBE", default=60)

    def test_lists_are_comma_separated_and_drop_blanks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROBE", " a , ,b ,")
        assert get_list("PROBE") == ["a", "b"]


class TestDatabaseUrl:
    def test_parses_credentials_host_port_and_name(self) -> None:
        parsed = parse_database_url("postgres://user:p%40ss@db:5432/gau")

        assert parsed["ENGINE"] == "django.db.backends.postgresql"
        assert parsed["NAME"] == "gau"
        assert parsed["USER"] == "user"
        # Percent-encoding must survive: passwords routinely contain @ and /.
        assert parsed["PASSWORD"] == "p@ss"
        assert parsed["HOST"] == "db"
        assert parsed["PORT"] == "5432"

    @pytest.mark.parametrize("url", ["sqlite:///db.sqlite3", "mysql://u:p@h/db"])
    def test_refuses_any_engine_other_than_postgresql(self, url: str) -> None:
        """A SQLite fallback would let tests pass against a database the
        platform never runs on — the content model needs JSONB and
        hierarchical queries."""
        with pytest.raises(ImproperlyConfigured, match="postgres"):
            parse_database_url(url)

    def test_refuses_a_url_that_names_no_database(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="does not name a database"):
            parse_database_url("postgres://user:pass@db:5432/")


class TestRedisUrl:
    @pytest.mark.parametrize("url", ["redis://redis:6379/0", "rediss://redis:6380/1"])
    def test_accepts_redis_schemes(self, url: str) -> None:
        assert parse_redis_url(url) == url

    def test_refuses_a_url_that_is_not_redis(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="redis"):
            parse_redis_url("http://redis:6379/0")
