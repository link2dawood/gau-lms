"""Routes owned by the content module, mounted at /api/ by core/urls.py."""

from __future__ import annotations

from django.urls import path

from apps.content import views

app_name = "content"

urlpatterns = [
    path("textbook/", views.TextbookView.as_view(), name="textbook"),
    # A uuid converter, so a malformed id is a 404 from the router rather than
    # a ValidationError from the ORM deeper in.
    path("books/<uuid:book_id>/toc/", views.BookTocView.as_view(), name="book-toc"),
    path("nodes/<uuid:node_id>/", views.NodeView.as_view(), name="node"),
]
