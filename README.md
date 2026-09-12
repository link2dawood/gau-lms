# GAU Interactive Textbook Platform

An LTI 1.3 tool launched from Canvas. It presents the GAU Professional Nursing
Textbook as structured, searchable web content, remembers each reader's
position, and gives content administrators a CMS with non-destructive version
history.

Canvas remains the authority for identity, courses, enrollment and roles. This
platform is the content and learning-experience layer.

## Quick start

```bash
cp .env.example .env    # then set DJANGO_SECRET_KEY, POSTGRES_PASSWORD, MEILI_MASTER_KEY
docker compose up -d --wait
```

Open `http://localhost:8080`. See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for
what each setting does.

## Documentation

| Document | For |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the platform is built, and why each rule exists |
| [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) | Every configuration variable |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branch strategy, commits, pull requests |
| [DECISIONS.md](DECISIONS.md) | Binding design decisions and their rationale |
| [PROGRESS.md](PROGRESS.md) | Phase 1 task board |

Canvas setup, deployment and the administrator guide are written in later tasks.

## Stack

Django 5.2 · Django REST Framework · PostgreSQL 16 · Redis 7.2 · Celery ·
Meilisearch · Next.js 14 · React 18 · TypeScript · Tailwind CSS · Nginx ·
Docker Compose · pytest · Playwright
