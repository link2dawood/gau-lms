"""Django admin for users.

Users come from Canvas launches only (rule C.5), so the admin cannot create
them, and the fields Canvas supplies are read-only. What an operator may
change is platform-owned: CMS access, Django admin access, and deactivation.
Course roles are not here, and never will be — they belong to Canvas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from apps.accounts.models import User

if TYPE_CHECKING:
    # django-stubs declares ModelAdmin as generic so the model type is known.
    # Django does not make it subscriptable at runtime, so writing
    # `admin.ModelAdmin[User]` as a base class raises TypeError the moment the
    # admin autodiscovers — which is during startup, taking the whole
    # application with it.
    ModelAdminBase = admin.ModelAdmin[User]
else:
    ModelAdminBase = admin.ModelAdmin


@admin.register(User)
class UserAdmin(ModelAdminBase):
    list_display = ("name", "email", "canvas_user_id", "is_content_admin", "is_active")
    list_filter = ("is_content_admin", "is_staff", "is_active")
    search_fields = ("name", "email", "canvas_user_id")
    ordering = ("name",)

    fields = (
        "id",
        "canvas_user_id",
        "name",
        "email",
        "avatar_url",
        "is_content_admin",
        "is_active",
        "is_staff",
        "last_login",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "id",
        "canvas_user_id",
        "name",
        "email",
        "avatar_url",
        "last_login",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
