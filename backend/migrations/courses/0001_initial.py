# Initial migration for courses and memberships.
#
# Written by hand while Docker was paused. `manage.py makemigrations --check`
# must report no changes before this is applied (task 1.6 verification).
#
# Amended by task 1.13 to add the Names and Roles fields. Amending rather
# than adding 0002 is safe only because no migration has ever been applied
# to any database (DECISIONS.md D-009); after the first `migrate` this would
# be a schema rewrite rather than a file edit.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("issuer", models.CharField(max_length=512)),
                ("platform_guid", models.CharField(blank=True, max_length=255)),
                ("canvas_course_id", models.CharField(max_length=255)),
                ("canvas_deployment_id", models.CharField(blank=True, max_length=255)),
                (
                    "nrps_context_memberships_url",
                    models.URLField(blank=True, max_length=1024),
                ),
                ("roster_synced_at", models.DateTimeField(blank=True, null=True)),
                ("title", models.CharField(blank=True, max_length=512)),
                ("label", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("title", "canvas_course_id"),
            },
        ),
        migrations.CreateModel(
            name="CourseMembership",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("STUDENT", "Student"),
                            ("FACULTY", "Faculty"),
                            ("ADMIN", "Administrator"),
                        ],
                        default="STUDENT",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="memberships",
                        to="courses.course",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="course",
            constraint=models.UniqueConstraint(
                fields=("issuer", "platform_guid", "canvas_course_id"),
                name="unique_course_per_platform_instance",
            ),
        ),
        migrations.AddConstraint(
            model_name="coursemembership",
            constraint=models.UniqueConstraint(
                fields=("course", "user"), name="unique_course_membership"
            ),
        ),
    ]
