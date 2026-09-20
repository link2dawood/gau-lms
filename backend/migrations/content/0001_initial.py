# Initial migration for books.
#
# Written by hand while Docker was paused. `manage.py makemigrations --check`
# must report no changes before this is applied (task 2.1 verification).

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Book",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("title", models.CharField(max_length=512)),
                ("slug", models.SlugField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("PUBLISHED", "Published"),
                            ("ARCHIVED", "Archived"),
                        ],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("title",),
            },
        ),
        migrations.CreateModel(
            name="ContentNode",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "node_type",
                    models.CharField(
                        choices=[
                            ("UNIT", "Unit"),
                            ("CHAPTER", "Chapter"),
                            ("SECTION", "Section"),
                            ("SUBSECTION", "Subsection"),
                        ],
                        max_length=16,
                    ),
                ),
                ("title", models.CharField(max_length=512)),
                ("position", models.PositiveIntegerField(default=0)),
                ("path", models.CharField(db_index=True, editable=False, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nodes",
                        to="content.book",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="content.contentnode",
                    ),
                ),
            ],
            options={
                "ordering": ("path", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="contentnode",
            constraint=models.CheckConstraint(
                condition=models.Q(title__gt=""), name="content_node_title_not_empty"
            ),
        ),
        migrations.AddConstraint(
            model_name="contentnode",
            constraint=models.CheckConstraint(
                condition=models.Q(path__gt=""), name="content_node_path_not_empty"
            ),
        ),
        migrations.AddIndex(
            model_name="contentnode",
            index=models.Index(fields=["book", "path"], name="content_node_tree_idx"),
        ),
        migrations.AddConstraint(
            model_name="book",
            constraint=models.CheckConstraint(
                condition=models.Q(title__gt=""), name="book_title_not_empty"
            ),
        ),
    ]
