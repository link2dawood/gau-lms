"""Every module's migrations live here, one package per app.

Django defaults to a `migrations/` folder inside each app. They are gathered in
one place instead so the full schema history of the platform can be read in
order without opening nine directories, and so a review of a change that spans
modules shows every migration side by side.

`MIGRATION_MODULES` in core/settings/base.py maps each app label to its package
here. Adding a module means adding a package below and an entry there, or Django
will silently treat the app as having no migrations.
"""
