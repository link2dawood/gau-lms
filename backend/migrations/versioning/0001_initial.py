# Initial migration for content versions.
#
# Written by hand while Docker was paused. `manage.py makemigrations --check`
# must report no changes before this is applied (task 2.4 verification). If it
# does report changes, regenerate this file rather than patching it.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.versioning.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("content", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentVersion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("version_number", models.PositiveIntegerField()),
                (
                    "body",
                    models.JSONField(
                        validators=[apps.versioning.models.validate_tiptap_document]
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("change_note", models.CharField(blank=True, max_length=500)),
                ("is_published", models.BooleanField(default=False)),
                (
                    "node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="versions",
                        to="content.contentnode",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="content_versions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "previous_version",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="succeeded_by",
                        to="versioning.contentversion",
                    ),
                ),
            ],
            options={
                "ordering": ("node", "-version_number"),
            },
        ),
        migrations.AddConstraint(
            model_name="contentversion",
            constraint=models.CheckConstraint(
                condition=models.Q(version_number__gte=1),
                name="content_version_number_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentversion",
            constraint=models.UniqueConstraint(
                fields=("node", "version_number"), name="unique_version_number_per_node"
            ),
        ),
        migrations.AddConstraint(
            model_name="contentversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_published=True),
                fields=("node",),
                name="one_published_version_per_node",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentversion",
            constraint=models.UniqueConstraint(
                fields=("previous_version",), name="unique_previous_version_link"
            ),
        ),
    ]
