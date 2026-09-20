"""Tests for the platform user model.

Assertions about behaviour Canvas-based identity depends on: one account per
Canvas person, no password a reader could use to bypass Canvas, CMS permission
independent of Django admin access, and an admin that cannot create or rename
people.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import RequestFactory

from apps.accounts.admin import UserAdmin
from apps.accounts.models import User
from tests.factories import UserFactory


class TestUserModelIsTheActiveModel:
    def test_the_platform_user_is_the_auth_user_model(self) -> None:
        assert get_user_model() is User

    def test_canvas_identity_is_the_login_field(self) -> None:
        assert User.USERNAME_FIELD == "canvas_user_id"


@pytest.mark.django_db
class TestCreatingUsers:
    def test_identifier_is_a_uuid_not_a_sequence(self) -> None:
        user = User.objects.create_user(canvas_user_id="sub-1")
        assert isinstance(user.pk, uuid.UUID)

    def test_a_reader_has_no_usable_password(self) -> None:
        """Canvas authenticates readers. A usable password would be a second way
        in that bypasses Canvas, which is exactly what rule C.5 forbids."""
        user = User.objects.create_user(canvas_user_id="sub-1", password="ignored")
        assert user.has_usable_password() is False

    def test_a_canvas_identity_is_required(self) -> None:
        with pytest.raises(ValueError, match="canvas_user_id"):
            User.objects.create_user(canvas_user_id="")

    def test_new_users_have_no_privileges(self) -> None:
        user = User.objects.create_user(canvas_user_id="sub-1")
        assert (user.is_content_admin, user.is_staff, user.is_superuser) == (False, False, False)
        assert user.is_active is True

    def test_one_canvas_person_is_one_account(self) -> None:
        """The 'no second account' acceptance criterion, enforced by the
        database rather than by application code that could be bypassed."""
        User.objects.create_user(canvas_user_id="sub-1")
        with pytest.raises(IntegrityError):
            User.objects.create_user(canvas_user_id="sub-1")

    def test_name_and_email_may_be_withheld_by_canvas(self) -> None:
        """Course privacy settings can suppress both claims."""
        user = User.objects.create_user(canvas_user_id="sub-1")
        assert (user.name, user.email) == ("", "")

    def test_two_people_may_share_an_email(self) -> None:
        User.objects.create_user(canvas_user_id="sub-1", email="shared@gau.edu")
        User.objects.create_user(canvas_user_id="sub-2", email="shared@gau.edu")
        assert User.objects.filter(email="shared@gau.edu").count() == 2

    def test_string_form_prefers_the_name(self) -> None:
        assert str(UserFactory(name="Ada Lovelace")) == "Ada Lovelace"
        assert str(UserFactory(canvas_user_id="sub-9", name="")) == "sub-9"


@pytest.mark.django_db
class TestPrivileges:
    def test_superuser_is_staff_and_superuser(self) -> None:
        user = User.objects.create_superuser(canvas_user_id="ops-1", password="a-long-passphrase")
        assert (user.is_staff, user.is_superuser) == (True, True)
        assert user.check_password("a-long-passphrase")

    def test_superuser_cannot_be_created_without_staff(self) -> None:
        with pytest.raises(ValueError, match="is_staff"):
            User.objects.create_superuser(canvas_user_id="ops-1", is_staff=False)

    def test_cms_access_is_independent_of_django_admin_access(self) -> None:
        """A content editor need not reach the Django admin, and an operator
        need not be able to edit the textbook."""
        editor = User.objects.create_user(canvas_user_id="sub-1", is_content_admin=True)
        operator = User.objects.create_superuser(canvas_user_id="ops-1")
        assert (editor.is_content_admin, editor.is_staff) == (True, False)
        assert operator.is_content_admin is False


class TestAdminCannotManufactureIdentity:
    def _admin(self) -> UserAdmin:
        return UserAdmin(User, admin.site)

    def test_users_cannot_be_added_by_hand(self) -> None:
        request = RequestFactory().get("/admin/accounts/user/add/")
        assert self._admin().has_add_permission(request) is False

    @pytest.mark.parametrize("field", ["id", "canvas_user_id", "name", "email", "avatar_url"])
    def test_fields_supplied_by_canvas_are_read_only(self, field: str) -> None:
        assert field in self._admin().readonly_fields

    @pytest.mark.parametrize("field", ["is_content_admin", "is_active", "is_staff"])
    def test_platform_owned_flags_remain_editable(self, field: str) -> None:
        assert field not in self._admin().readonly_fields


@pytest.mark.django_db
def test_models_and_migrations_are_in_sync() -> None:
    """Fails if a model changes without a migration — or if a migration was
    written by hand and does not match its model, as 0001_initial was."""
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
