"""Django admin for users.

Users come from Canvas launches only (rule C.5), so the admin cannot create
them, and the fields Canvas supplies are read-only. What an operator may
change is platform-owned: CMS access, Django admin access, and deactivation.
Course roles are not here, and never will be — they belong to Canvas.
"""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
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
