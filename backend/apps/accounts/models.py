"""The platform's user record.

Canvas is the authority for identity (architecture rule C.5). A User row is a
local reference to a Canvas person, created by the launch provisioning service
(task 1.8) — never by a sign-up form, and never with a password a reader could
use to log in around Canvas.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.accounts.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    # Stable internal identifier (rule C.2). Other modules and every learning
    # record refer to this, never to the Canvas id, so a change in how Canvas
    # identifies people touches one column rather than every table.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The LTI 1.3 `sub` claim for this person on the configured Canvas
    # platform. Unique, because one Canvas person must map to exactly one
    # platform account — the "no second account" acceptance criterion.
    canvas_user_id = models.CharField(max_length=255, unique=True)

    # Refreshed from launch claims on every launch (task 1.8). Canvas may
    # withhold name and email depending on the course's privacy settings, so
    # both may be blank, and email is not unique.
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    avatar_url = models.URLField(max_length=2048, blank=True)

    # Platform permission to use the CMS (task 3.1). Deliberately not derived
    # from a Canvas role: a course Teacher is not automatically a textbook
    # editor. Granted to the administrators GAU names.
    is_content_admin = models.BooleanField(default=False)

    # Django admin access for platform operators. Unrelated to Canvas roles and
    # to is_content_admin.
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "canvas_user_id"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.name or self.canvas_user_id
