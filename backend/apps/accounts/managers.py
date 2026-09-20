"""Manager for the platform user model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    from apps.accounts.models import User


class UserManager(BaseUserManager["User"]):
    """Creates users keyed on their Canvas identity.

    Readers never have a password: Canvas authenticates them and the platform
    trusts the signed launch (task 1.5). `create_user` therefore always stores
    an unusable password. Only `create_superuser`, for operators of the Django
    admin, accepts one.
    """

    def create_user(self, canvas_user_id: str, **extra_fields: Any) -> User:
        if not canvas_user_id:
            raise ValueError("A user must have a canvas_user_id.")
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(canvas_user_id=canvas_user_id, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self, canvas_user_id: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        user = self.model(canvas_user_id=canvas_user_id, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user
