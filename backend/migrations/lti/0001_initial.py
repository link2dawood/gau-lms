# Initial migration for Canvas platform registrations.
#
# Written by hand while Docker was paused. `manage.py makemigrations --check`
# must report no changes before this is applied (task 1.2 verification).
#
# Amended by task 1.15 to add the launch audit log. Amending rather than
# adding 0002 is safe only because no migration has ever been applied to any
# database (DECISIONS.md D-009).

import uuid

from django.db import migrations, models

import apps.lti.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LtiPlatform",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("issuer", models.CharField(max_length=512)),
                ("client_id", models.CharField(max_length=255)),
                (
                    "deployment_ids",
                    models.JSONField(
                        default=list,
                        validators=[apps.lti.models.validate_deployment_ids],
                    ),
                ),
                ("auth_login_url", models.URLField(max_length=512)),
                ("auth_token_url", models.URLField(max_length=512)),
                ("jwks_url", models.URLField(max_length=512)),
                ("tool_key_id", models.CharField(blank=True, max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "LTI platform",
                "verbose_name_plural": "LTI platforms",
                "ordering": ("issuer", "client_id"),
            },
        ),
        migrations.CreateModel(
            name="LtiLaunchLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("ACCEPTED", "Accepted"),
                            ("DEEP_LINK", "Deep linking request answered"),
                            ("REFUSED_VALIDATION", "Refused: could not be verified"),
                            ("REFUSED_CONFIGURATION", "Refused: platform not configured"),
                            ("REFUSED_CLAIMS", "Refused: launch carried too little"),
                            ("ERROR", "Failed unexpectedly"),
                        ],
                        max_length=32,
                    ),
                ),
                ("issuer", models.CharField(blank=True, max_length=512)),
                ("client_id", models.CharField(blank=True, max_length=255)),
                ("deployment_id", models.CharField(blank=True, max_length=255)),
                ("canvas_user_id", models.CharField(blank=True, max_length=255)),
                ("nonce", models.CharField(blank=True, max_length=255)),
                ("user_id", models.UUIDField(blank=True, null=True)),
                ("course_id", models.UUIDField(blank=True, null=True)),
                ("role", models.CharField(blank=True, max_length=16)),
                ("detail", models.CharField(blank=True, max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "LTI launch log",
                "verbose_name_plural": "LTI launch logs",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="ltilaunchlog",
            index=models.Index(fields=["-created_at"], name="lti_launch_recent_idx"),
        ),
        migrations.AddIndex(
            model_name="ltilaunchlog",
            index=models.Index(fields=["canvas_user_id"], name="lti_launch_user_idx"),
        ),
        migrations.AddConstraint(
            model_name="ltiplatform",
            constraint=models.UniqueConstraint(
                fields=("issuer", "client_id"), name="unique_lti_registration"
            ),
        ),
    ]
