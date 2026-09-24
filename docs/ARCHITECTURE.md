# Architecture

How the GAU Interactive Textbook Platform is put together, and — more usefully —
why. The rules here exist because each one prevents a specific, expensive
failure; the reasoning is recorded alongside the rule so it can be weighed
rather than merely obeyed.

**Audience:** engineers working on the codebase, now and in later phases.

**Status:** first draft, written at the end of Stage 0. Everything marked
**built** exists and is verified. Everything marked with a task number is
designed but not yet built, and that task is where it lands. Binding decisions
are numbered `D-nnn` and recorded in full in [`DECISIONS.md`](../DECISIONS.md).

- [What the platform is](#what-the-platform-is)
- [System overview](#system-overview)
- [Request paths](#request-paths)
- [Backend modules](#backend-modules)
- [The rules, and what each one prevents](#the-rules-and-what-each-one-prevents)
- [Content model](#content-model)
- [Frontend](#frontend)
- [Background work](#background-work)
- [Configuration](#configuration)
- [Testing](#testing)
- [Local development and CI](#local-development-and-ci)
- [Extending the platform in later phases](#extending-the-platform-in-later-phases)

---

## What the platform is

An **LTI 1.3 tool** launched from Canvas. It presents a 338-page nursing textbook
as structured, searchable web content, remembers where each reader stopped, and
gives content administrators a CMS with non-destructive version history.

The single most important boundary:

> **Canvas is the authority for identity, courses, enrollment, terms and roles.
> This platform is the content and learning-experience layer. It is never a
> second LMS.**

Almost every architectural rule below follows from taking that sentence
seriously. The platform has no sign-up, no password login for readers, no
enrollment screen and no role editor — each of those would be a second source of
truth that disagrees with Canvas sooner or later.

---

## System overview

```
                         Canvas LMS
                             │  LTI 1.3 launch (OIDC + signed JWT)
                             ▼
  Browser ─────────────▶  Nginx  ── single public entry point
                             │
              ┌──────────────┴───────────────┐
              │ /api /lti /admin             │ everything else
              ▼                              ▼
     Django + Gunicorn               Next.js (App Router)
     backend                         frontend
       │   ▲                              │
       │   └── server-side renders call ──┘
       │       Django directly over the private network
       │
       ├──▶ PostgreSQL 16   content, versions, users, reading positions
       ├──▶ Redis 7.2       cache, sessions, Celery broker, LTI nonces
       └──▶ Meilisearch     block-level full-text search          (task 2.11)

     Celery worker + beat  ──▶ same PostgreSQL, Redis, Meilisearch
```

All eight services run under Docker Compose on one private bridge network.
PostgreSQL, Redis and Meilisearch are never exposed outside that network in a
deployed environment; locally they bind to `127.0.0.1` only.

It is a **modular monolith**: one Django project and one Next.js app, internally
divided into bounded modules that communicate through documented service
interfaces. This keeps deployment, testing and handover simple for Phase 1, while
leaving any single module — most likely the AI assistant or analytics in a later
phase — separable into its own service without rewriting the core.

| Layer | Technology | Status |
|---|---|---|
| Backend | Django 5.2 LTS, Python 3.12, Django REST Framework | **built** |
| LTI 1.3 | PyLTI1p3 | **built** — OIDC login and launch validation (1.4, 1.5) |
| Database | PostgreSQL 16 | **built** |
| Search | Meilisearch 1.12 | running; indexing in task 2.11 |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS | **built** |
| Content editor | Tiptap (ProseMirror) | task 3.5 |
| Document conversion | Pandoc, Poppler | installed in the backend image; pipeline in task 3.11 |
| Cache and queues | Redis 7.2, Celery, Celery Beat | **built** |
| Edge | Nginx, Gunicorn | **built** |
| Testing | pytest, Playwright | **built** |
| CI | GitHub Actions | **written**; not yet run on GitHub |

The stack is fixed. Adding a runtime dependency outside it requires an approved
entry in `DECISIONS.md`.

---

## Request paths

Nginx splits the URL space at the edge (`docker/nginx/conf.d/app.conf`):

| Path | Served by | Notes |
|---|---|---|
| `/api/` | Django | JSON API. Default-deny; see D-012. |
| `/lti/` | Django | JWKS, OIDC login, launch and ticket exchange **built**; deep linking in task 1.14. Unauthenticated by design — Canvas reaches these before any session exists, and they set their own `frame-ancestors` policy (D-031). |
| `/admin/` | Django | Django admin, for staff only. |
| `/static/` | Nginx, from disk | Django's collected static files. |
| `/media/` | Nginx, from disk | Figures and illustrations uploaded through the CMS. |
| everything else | Next.js | Reader, faculty dashboard, CMS screens. |

### A page load

1. The browser requests a reader page. Nginx forwards it to Next.js.
2. A React Server Component calls Django **directly over the private network**,
   not back out through Nginx — `INTERNAL_API_BASE_URL` (D-016). This keeps the
   critical path for first paint of long-form content short.
3. Django answers; Next.js renders HTML and streams it back.
4. Later requests from the browser — saving a reading position, running a
   search — go same-origin through Nginx, so the session cookie is sent.

### A Canvas launch *(steps 1–4 built in tasks 1.4–1.9; role routing in 1.12)*

1. Canvas POSTs an OIDC login initiation to `/lti/login/`. The platform
   generates `state` and a `nonce`, stores both in Redis with a short expiry
   (logical database 3), and redirects to Canvas's authorisation endpoint.
2. Canvas POSTs a signed JWT to `/lti/launch/`. PyLTI1p3 validates the
   signature, issuer, audience, expiry, deployment id, and that the nonce has not
   been used before.
3. The provisioning service upserts the user, course and membership from the
   launch claims **in one transaction**. A first launch creates the user; a
   repeat launch never creates a second account.
4. A session is established and the browser is redirected to the frontend with
   a short-lived, single-use launch ticket. Because the reader runs inside a
   Canvas iframe its cookie is cross-site, so it is `SameSite=None; Secure;
   HttpOnly` — which is why Nginx forwards `X-Forwarded-Proto` and Django
   trusts it (`SECURE_PROXY_SSL_HEADER`). A browser that blocks third-party
   cookies discards that cookie silently; the ticket is what lets the
   new-window fallback (task 1.10) establish a session from a first-party
   context, by posting it to `/lti/session/`.
5. The frontend routes by role: student to the reader, faculty to the dashboard,
   administrators offered the CMS.

---

## Backend modules

`backend/` is laid out as follows. Modules marked with a task number do not exist
yet; `core/settings/base.py` lists them in `LOCAL_APPS`, commented, in the
order they arrive.

```
backend/
  core/                   platform configuration                       built
    settings/
      env.py              typed environment and secrets loader (D-011)
      base.py             shared settings
      dev.py  prod.py  test.py
    celery.py             Celery app and queue routing (D-013)
    health.py             readiness and liveness endpoints
    urls.py               root URL map
    wsgi.py  asgi.py
  migrations/             every module's migrations, in one place      built
    accounts/             mapped by MIGRATION_MODULES (D-024)
  apps/
    accounts/             User, role normalisation                     task 1.1
    lti/                  launch, OIDC, JWKS, deep linking, NRPS       platforms, keys, JWKS, login, launch, session (1.2–1.9)
    courses/              Course, CourseMembership, CourseBook         task 1.6
    content/              Book, ContentNode, tree service              task 2.1
    versioning/           ContentVersion, publish, diff, restore       task 2.4
    reader/               ReadingPosition, next/previous               task 2.9
    search/               Meilisearch client and indexers              task 2.11
    cms/                  admin API for hierarchy and editing          task 3.1
    imports/              Pandoc/Poppler pipeline                      task 3.11
  utils/                  shared utilities, added with the first one
  tests/
```

Migrations are gathered rather than kept inside each app, so the schema history
of the platform reads in order and a change spanning modules shows its
migrations together (D-024). Django finds them only through `MIGRATION_MODULES`
in `core/settings/base.py`: an app added without an entry there is treated as
having no migrations and its tables are never created, which
`tests/test_structure.py` guards against.

### Module boundaries

Each module exposes a `services.py`. **Other modules call those services; they
never import another module's models or query its tables directly.**

```python
# Correct — through the owning module's service interface
from apps.content import services as content
toc = content.table_of_contents(book_id)

# Not permitted — reaches into another module's tables
from apps.content.models import ContentNode
ContentNode.objects.filter(book_id=book_id)
```

Without this rule every module ends up coupled to every other module's schema,
and the monolith cannot be split later — the whole reason for building it as
*modular* is lost. It also gives Phase 2 a real contract to build against
instead of a set of tables it has to reverse-engineer.

---

## The rules, and what each one prevents

These are non-negotiable. The pull-request template carries each as a checklist
item (D-003).

| # | Rule | What breaks without it |
|---|---|---|
| C.1 | **Modular monolith.** Cross-module access through `services.py` only. | Modules couple to each other's schemas; nothing can be separated later. |
| C.2 | **Stable identifiers.** Every book, unit, chapter, section, subsection and content block has a UUID. Page numbers are never identity. Slugs may change; UUIDs never do. | A re-paginated or reorganised edition silently breaks every saved reading position, search result and deep link into the old structure. |
| C.3 | **Non-destructive versioning.** Publishing creates a new immutable `ContentVersion`. Existing rows are never updated or deleted. Restoring an old version creates a new version. | No way to show what a student actually read on a given date, or to recover from a bad publish. |
| C.4 | **Separation of records.** Content, content versions and learning records live in separate tables. A content update never mutates a learning record. | Correcting a typo resets hundreds of students' reading positions. |
| C.5 | **Canvas is authoritative.** No manual enrollment, course creation or role assignment in production code paths. | Two sources of truth for who may see what, which diverge the first time someone is dropped from a course. |
| C.6 | **No hard-coding.** No user ids, course ids, role strings, Canvas URLs, client ids or deployment ids in code. | The platform works for one Canvas instance and one course, and breaks on the second. |
| C.7 | **Structured content.** Bodies are Tiptap JSON, and every top-level node carries a `blockId` UUID in its attributes. | No stable anchor for search results, reading positions or future annotations; every edit reshuffles them. |
| C.8 | **Every endpoint is authorised.** Default deny. Every request is scoped to the course resolved at launch. | One forgotten permission class exposes content across courses. |
| C.9 | **Published only for readers.** Students and faculty see published content. Drafts are visible only in CMS preview. | Half-finished edits appear to students mid-semester. |
| C.10 | **Async for slow work.** Imports, indexing and roster sync are Celery tasks, never inline in a request. | Converting the textbook times out the request that started it, and blocks a Gunicorn worker while doing so. |

### Default deny, concretely

DRF's own default is `AllowAny`. This platform sets
`DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` (D-012), so a view that forgets
to declare a permission class **fails closed** — a 403 in testing rather than an
exposure in production.

The only deliberately unauthenticated routes are `/api/health/` and
`/api/live/`, because a load balancer cannot present a Canvas session. They are
plain Django views, touch no domain data, and return no version, hostname or
error detail.

---

## Content model

*Designed; built in Stage 2.*

```
Book ─┬─ ContentNode (UNIT)
      │    └─ ContentNode (CHAPTER)
      │         └─ ContentNode (SECTION)
      │              └─ ContentNode (SUBSECTION)
      │
      └─ each ContentNode ──▶ ContentVersion, ContentVersion, …   (immutable, append-only)
                                  │
                                  └─ body: Tiptap JSON, every top-level node
                                           carrying a stable blockId

ReadingPosition ── user, book, node, blockId, scroll ratio     (a learning record)
```

Three things are kept apart on purpose:

- **Structure** — `Book` and `ContentNode`, the hierarchy and its ordering.
- **Content** — `ContentVersion`, the immutable history of what a node said.
- **Learning records** — `ReadingPosition` now, progress and annotations later.

A `ReadingPosition` points at a node UUID and a block UUID, never at a version
and never at a page. When an administrator publishes a correction, a new
`ContentVersion` is created, the node and block identifiers are unchanged, and
every student's position still resolves. That is rule C.4 doing its job.

Block identifiers are assigned when a block is created and **preserved on edit**
(task 3.5). An edit that regenerated them would orphan every position and search
hit pointing into the section.

---

## Frontend

`frontend/` is a Next.js 14 App Router application in strict TypeScript.

```
frontend/
  app/                  routes                                   built
  components/           reader, Tiptap renderer, editor, TOC     task 2.7 onward
  lib/
    config.ts           API base URL per execution context (D-016)
    api/
      client.ts         typed request(), returning ApiResult<T>
      errors.ts         ApiError kinds and user-safe messages
      health.ts         the worked example every binding follows
  tests/e2e/            Playwright specs
```

### Calling the API

Every call returns an `ApiResult<T>` — a discriminated union of success or a
described failure — rather than throwing (D-014):

```ts
const result = await fetchHealth();
if (!result.ok) {
  // result.error.kind: 'network' | 'malformed' | 'unauthenticated'
  //                  | 'forbidden' | 'not_found' | 'client' | 'server'
  return <p>{result.error.message}</p>;
}
// TypeScript will not allow result.data to be read before the check above.
```

The reader must show a different screen for an expired launch, a node outside
the course, and an unreachable backend. A thrown `Error` would flatten those into
a string; a union makes each one a case the compiler insists is handled.

Responses are **validated by a guard, never cast** (D-015). Each binding ships a
`parseX` function beside its type that narrows `unknown` to the expected shape or
returns `null`. When the backend contract changes, the failure is one explicit
`malformed` error at the boundary — not an `undefined` surfacing deep inside a
component, three files from the cause.

### Adding a binding

Copy `lib/api/health.ts`:

1. Declare the response type.
2. Write `parseX(value: unknown): X | null`. For nested content structures,
   validate recursively, not just the outer shape.
3. Export a function returning `request(path, parseX, options)`.

### Type strictness

TypeScript runs with `strict`, `noUncheckedIndexedAccess` and
`exactOptionalPropertyTypes`, and ESLint rejects `any`. The second of these
matters most for the content tree: indexing into a node's children yields
`T | undefined`, and the tree code has to handle the missing case rather than
assert it away.

### Styling

Design tokens are CSS custom properties in `app/globals.css`, referenced from
`tailwind.config.ts`. No component hard-codes a colour, so GAU branding in task
4.5 changes token values rather than components.

---

## Background work

Celery runs slow work off the request path. Queues are separated **by cost**
(D-013), so a long job cannot starve a short one:

| Queue | Work | Task |
|---|---|---|
| `imports` | Converting Word, EPUB, HTML and PDF sources — minutes | 3.11 |
| `indexing` | Meilisearch synchronisation after a publish — seconds | 2.12 |
| `canvas` | Names and Roles roster synchronisation | 1.13 |
| `default` | Everything else | — |

On a single queue, a 338-page PDF import would delay the reindex triggered by an
administrator pressing Publish, and they would see stale search results with no
explanation. Routing is by module path, so task modules must live at
`apps.<module>.tasks`.

---

## Configuration

Every setting comes from the environment through one typed reader,
`core/settings/env.py`, which fails loudly on missing or malformed values
rather than guessing. Production settings refuse to start when a security-
critical value is absent.

The full reference — every variable, its default, and the consequence of getting
it wrong — is [`docs/ENVIRONMENT.md`](ENVIRONMENT.md).

---

## Testing

| Suite | Tool | Runs against | Status |
|---|---|---|---|
| Backend | pytest, pytest-django, factory_boy | A real PostgreSQL test database — never SQLite | **built** |
| End-to-end | Playwright, desktop and mobile | The real stack through Nginx — no mocked API | **built** |

Two choices worth understanding:

- **End-to-end tests do not mock the API** (D-017). Nearly everything that breaks
  a Canvas launch lives in the chain rather than in a component — cookie
  attributes, forwarded scheme, iframe headers, redirects. A suite that stubbed
  the backend would pass while launches failed.
- **They run against the production frontend build** (D-021). The dev server
  compiles routes on first request; a cold page took 29 seconds, which made the
  suite flaky while measuring nothing about the product.

Retries are enabled in CI only (D-019). A test that passes only on retry is a
broken test, and locally the flake stays visible while it can still be
diagnosed.

---

## Local development and CI

```bash
cp .env.example .env              # then set the three required secrets
docker compose up -d --wait       # development: Next.js dev server, fast refresh
```

| Command | Gives you |
|---|---|
| `docker compose up` | Development. Loads `docker-compose.override.yml`, which swaps in the Next.js dev server with source mounted. |
| `docker compose -f docker-compose.yml up` | The production build. What CI runs, and the base the server extends in task 4.8. |
| `docker compose run --rm backend python manage.py migrate` | Applies migrations. **Never automatic** (D-020). |

Migrations are deliberately not run on container start. Doing so makes replicas
race to migrate the same database during a rolling deploy, and means nobody
chooses when a schema change lands.

> **No migration has been applied yet.** The custom user model and the first
> migration land together in task 1.1 (D-009). Running `migrate` before then bakes
> Django's default user model into the migration state, and undoing that is a
> data migration rather than a setting change.

CI (`.github/workflows/ci.yml`) runs three jobs on every pull request:

- **backend** — ruff lint, ruff format, mypy strict, pytest with coverage
- **frontend** — ESLint, TypeScript, production build
- **e2e** — needs both; brings the stack up and runs Playwright

---

## Extending the platform in later phases

Phase 1 builds foundations and exposes service interfaces. It deliberately does
**not** build AI features, assessments, annotations, analytics or messaging.

Later phases are expected to attach at these points:

| Later capability | Attaches to |
|---|---|
| Annotations and highlights | `blockId` anchors on content blocks, and the learning-record tables |
| Progress and analytics | `ReadingPosition` and future learning records, via the reader service |
| AI learning assistant | The content service and search index; separable into its own service if needed |
| Deeper Canvas linking | Deep Linking, which returns content items addressed by node UUID (task 1.14) |
| Faculty communication | The course and membership services |

Because each module is reached only through its service interface, any of these
can be added — or split out — without reaching into the tables of the modules it
depends on.

*Module-level service interface notes are completed in task 4.10.*
