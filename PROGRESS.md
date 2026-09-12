# PROGRESS — GAU Interactive Textbook Platform, Phase 1

Task board for the build loop. One task per loop. Status values: `TODO`,
`IN PROGRESS`, `DONE`, `BLOCKED`.

A task is `DONE` only when a passing test or a verified command proved it.
A task is `BLOCKED` with the specific question recorded inline, so the next loop
does not repeat the work.

**Current status:** Stage 0 in progress. Next task: **0.6**.

---

## Stage 0: Foundations

| Id | Task | Depends on | Status |
|---|---|---|---|
| 0.1 | Git repo, `.gitignore`, branch strategy, PR template `[micro]` | — | **DONE** |
| 0.2 | Docker Compose: postgres, redis, meilisearch, backend, frontend, celery worker, celery beat, nginx | 0.1 | **DONE** |
| 0.3 | Django project with split settings, `.env.example` listing every variable | 0.2 | **DONE** |
| 0.4 | Next.js 14 app with TypeScript, Tailwind, path aliases, typed API client shell | 0.2 | **DONE** |
| 0.5 | pytest and Playwright configured, one smoke test each | 0.3, 0.4 | **DONE** |
| 0.6 | GitHub Actions: ruff, mypy, pytest, eslint, tsc, next build | 0.5 | TODO |
| 0.7 | `docs/ARCHITECTURE.md` and `docs/ENVIRONMENT.md` first draft | 0.3 | TODO |

**0.1 notes —** Repository root is the project root (no nested `gau-textbook/`
directory); `backend/`, `frontend/`, `docs/` sit directly at the top level. See
`DECISIONS.md` D-001. Branch strategy, commit convention and PR gate are in
`CONTRIBUTING.md`; the PR template encodes the Section C architecture rules as a
per-PR checklist. `.gitignore` covers Python, Node, Docker volumes, env files and
private keys — `.env.example` is the one env file that is committed.

**0.2 notes —** All eight services defined in `docker-compose.yml`; Dockerfiles
and Nginx configuration in `docker/` (DECISIONS.md D-005). Verified running:
PostgreSQL 16.15, Redis 7.2.16 with AOF persistence, Meilisearch 1.12.8
rejecting unauthenticated requests. Nginx routing proven against probe upstreams
— `/api/ /lti/ /admin/` to the backend, `/static/ /media/` served from disk,
everything else to Next.js — with the full `X-Forwarded-*` set surviving, which
task 1.9 depends on for `SameSite=None; Secure` cookies. Backend `base` image
builds with Python 3.12.14, Pandoc 2.17.1.1 (docx/epub/html) and Poppler 22.12.

Carried forward to the next loops:

- The **backend `dev`/`prod` stages** install from `backend/pyproject.toml` and
  the **frontend image** installs from `frontend/package-lock.json`. Neither
  manifest exists yet, so those image builds are first exercised by **0.3** and
  **0.4** respectively. The `base` stage — the part carrying real risk, the
  document-conversion toolchain — is built and verified now.
- Compose reads `.env`; copy `.env.example` and set `POSTGRES_PASSWORD` and
  `MEILI_MASTER_KEY`, which have no defaults and fail fast if unset.
- Host ports are configurable because collisions are common: on this machine
  5432 and 5433 were already held by unrelated projects, and verification ran
  with `POSTGRES_HOST_PORT=5434`.
- Named volumes `pg_data`, `redis_data`, `meili_data` persist across `down`.
- BuildKit image builds hit a transient `deb.debian.org` fetch failure once and
  succeeded unchanged on retry; not a configuration fault.

**0.3 notes —** Django 5.2 LTS project at `backend/`. Settings split four ways:
`env.py` (typed stdlib reader, D-011), `base.py`, `dev.py`, `prod.py`, plus
`test.py` for the suite in 0.5. `config/` holds urls, wsgi, asgi, celery and the
readiness endpoint; `apps/` is an empty namespace each module joins with its own
task, listed commented-out in `LOCAL_APPS` so the intended set is visible.

Points the next loops must respect:

- **No migration has been run against any database.** `AUTH_USER_MODEL` points
  at `accounts.User`, which task **1.1** creates; the first `migrate` happens
  there (DECISIONS.md D-009). The compose `backend` service migrates on start,
  so it is not brought up until 1.1.
- DRF **defaults to `IsAuthenticated`** (D-012). A view that forgets its
  permission class fails closed. `/api/health/` and `/api/live/` are the only
  unauthenticated routes and are plain Django views returning no detail.
- Production settings **refuse to start** without `DJANGO_ALLOWED_HOSTS`,
  `DJANGO_CSRF_TRUSTED_ORIGINS`, or with `MEILI_ENV` other than `production`.
- Celery queues `imports`, `indexing`, `canvas`, `default` are routed by module
  path (D-013), so task modules must live at `apps.<module>.tasks`.
- `.env.example` now carries 41 variables. Any new setting is added there in the
  same PR that reads it.

**Found during 0.2/0.3 verification, for task 4.8:** Nginx resolves upstream
hostnames once at startup and refuses to start if either is unresolvable, so a
restart while the frontend container is down takes `/api/` and `/lti/` down with
it even though the backend is healthy. Compose gates this with `depends_on` and
restarts on failure, so the window is narrow, but for an LTI tool a failed
launch is expensive. 4.8 should proxy through a variable with a `resolver`,
deferring resolution to request time — which costs upstream keepalive, so the
trade belongs with the production deployment. Documented in
`docker/nginx/conf.d/app.conf`.

**0.4 notes —** Next.js 14.2.33 / React 18.3.1 / TypeScript 5.6.3 / Tailwind
3.4.17, all pinned exactly and locked. App Router with layout, status page,
`not-found` and an `error` boundary. Path aliases `@/*`, `@/lib/*`,
`@/components/*`.

The API client is the substantive piece. Calls return `ApiResult<T>` rather than
throwing (D-014), responses are validated by a guard rather than cast (D-015),
and the base URL resolves per execution context (D-016). `lib/api/health.ts` is
the worked example every later binding copies: response type, `parseX` guard,
typed function.

Points the next loops must respect:

- **Do not run `npm run build` inside the `dev` image.** That stage pins
  `NODE_ENV=development`, so Next mixes dev and production React runtimes and
  prerendering fails with a `useContext` error that looks like an application
  bug. The production build belongs to the `builder` stage — build the `prod`
  target.
- TypeScript runs with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.
  Indexing into a content node's children yields `T | undefined`, which the
  tree code in task 2.3 must handle rather than assert away.
- `next.config.mjs` sets `ignoreDuringBuilds` for ESLint (linting is its own CI
  step in 0.6) but **not** for TypeScript — a type error fails the build.
- Design tokens are CSS custom properties in `app/globals.css`, referenced from
  `tailwind.config.ts`. GAU branding in task 4.5 changes values there; no
  component hard-codes a colour.
- `frontend/node_modules` is a named volume in compose. It is populated from the
  image on first use, so after changing dependencies the volume must be removed
  or it will serve the old tree.

**0.5 notes —** Both harnesses run and both were shown to fail when the thing
they test is genuinely broken.

Commands, for task 0.6 to wire verbatim:

```
# Backend — 9 tests, needs postgres+redis up
docker compose up -d --wait postgres redis meilisearch
docker run --rm --network gau-textbook_gau_net --env-file .env \
  -v "$PWD/backend:/app" -w /app gau-textbook-backend:dev pytest

# End-to-end — 8 tests across two viewports, needs the whole stack up
docker run --rm --network gau-textbook_gau_net -v "$PWD/frontend:/work" -w /work \
  -e PLAYWRIGHT_BASE_URL=http://nginx \
  mcr.microsoft.com/playwright:v1.63.0-noble \
  sh -c 'npm ci && npx playwright test'
```

Points the next loops must respect:

- pytest pins its own settings with `--ds=config.settings.test` in `addopts`
  (D-018). Setting `DJANGO_SETTINGS_MODULE` in the ini section does **not**
  work: pytest-django reads the environment first, and the container is run
  with `--env-file .env`, so the suite silently ran under dev settings.
- E2E has no `webServer` block and does not mock the API (D-017). It needs the
  stack up. `PLAYWRIGHT_BASE_URL` is `http://nginx` inside the compose network,
  `http://localhost:8080` from the host.
- The Playwright library version and the browser image tag must be changed
  together — currently both 1.63.0.
- Retries are CI-only (D-019), so a flake is visible locally the moment it
  appears rather than absorbed.
- `tests/test_smoke.py::TestConfiguration::test_no_custom_user_model_is_declared_yet`
  guards D-009 and **must be deleted by task 1.1** when the custom user model
  lands — it asserts the absence that 1.1 removes.

---

## Stage 1: Deliverable 1 — Canvas LMS Integration

| Id | Task | Depends on | Status |
|---|---|---|---|
| 1.1 | `accounts.User` model: uuid pk, canvas_user_id unique, name, email, avatar_url, is_content_admin | 0.3 | TODO |
| 1.2 | `lti.LtiPlatform` model: issuer, client_id, deployment_ids, auth_login_url, auth_token_url, jwks_url, tool private key reference — from env or fixtures, never hard-coded | 0.3 | TODO |
| 1.3 | Tool RSA keypair generation management command plus public JWKS endpoint `/lti/jwks/` | 1.2 | TODO |
| 1.4 | OIDC login initiation `/lti/login/`: state and nonce generation, stored in Redis with TTL, redirect to Canvas auth URL | 1.3 | TODO |
| 1.5 | Launch endpoint `/lti/launch/`: PyLTI1p3 validation of signature, issuer, aud, nonce replay, exp/iat, deployment id; clear error page on any failure | 1.4 | TODO |
| 1.6 | `courses.Course` and `courses.CourseMembership` models keyed on Canvas ids | 1.1 | TODO |
| 1.7 | Role normalisation service: LTI role URIs to `STUDENT`, `FACULTY`, `ADMIN`; unknown roles default to lowest privilege | 1.6 | TODO |
| 1.8 | Launch provisioning service: upsert user, course and membership from launch claims in one transaction; first launch creates the user, never a second account | 1.5, 1.7 | TODO |
| 1.9 | Session establishment for iframe context: signed session cookie `SameSite=None; Secure; HttpOnly`, short-lived launch token handed to the frontend | 1.8 | TODO |
| 1.10 | New-window launch fallback for browsers blocking third-party cookies, with an "open textbook" interstitial | 1.9 | TODO |
| 1.11 | `CourseScoped` permission and middleware: every request carries the launch course context; 403 on any other course | 1.9 | TODO |
| 1.12 | Role routing on the frontend `/launch` page: student to reader, faculty to dashboard, admin offered CMS | 1.9 | TODO |
| 1.13 | NRPS roster sync Celery task: fetch memberships, reconcile additions and removals, scheduled and on-demand | 1.8 | TODO |
| 1.14 | Deep Linking request and response handler (foundation): accept a deep link request, return a content item pointing at a node UUID | 1.5 | TODO |
| 1.15 | `lti.LtiLaunchLog` audit model: nonce, user, course, role, timestamp, outcome | 1.5 | TODO |
| 1.16 | Tests: valid launch, expired token, wrong aud, replayed nonce, unknown role, cross-course 403, first-launch provisioning, repeat-launch idempotency | 1.11 | TODO |
| 1.17 | `docs/CANVAS_SETUP.md` plus the tool JSON configuration for the Canvas admin | 1.5 | TODO |

---

## Stage 2: Deliverable 2 — Interactive Textbook Reader

| Id | Task | Depends on | Status |
|---|---|---|---|
| 2.1 | `content.Book` model: uuid, title, slug, description, status, created/updated | 0.3 | TODO |
| 2.2 | `content.ContentNode` model: uuid, book fk, parent fk, node_type (UNIT, CHAPTER, SECTION, SUBSECTION), title, position, materialised ancestry for efficient tree reads | 2.1 | TODO |
| 2.3 | Tree service: full TOC in one query, resolve ancestors, flat reading order, next and previous across sibling and parent boundaries | 2.2 | TODO |
| 2.4 | `versioning.ContentVersion` model: uuid, node fk, version_number, body (JSONB Tiptap), created_by, created_at, change_note, is_published, previous_version fk | 2.2 | TODO |
| 2.5 | `courses.CourseBook` mapping model plus service resolving which book a launched course opens | 2.1, 1.6 | TODO |
| 2.6 | Read API: `GET /api/books/:id/toc`, `GET /api/nodes/:id` returning published body plus prev/next, course-scoped and permission-checked | 2.3, 2.5, 1.11 | TODO |
| 2.7 | Tiptap JSON renderer in React: headings, paragraphs, lists, tables with headers, figures with captions and alt text, blockquotes, callouts, references, links; every top-level node renders with `id={blockId}` | 0.4 | TODO |
| 2.8 | Reader layout: collapsible TOC sidebar, breadcrumb, content pane, previous/next controls, mobile drawer TOC, sticky progress indicator | 2.6, 2.7 | TODO |
| 2.9 | `reader.ReadingPosition` model: user, book, node, block_id, scroll_ratio, updated_at, unique per user and book | 2.2 | TODO |
| 2.10 | Position save (debounced PATCH on section change and scroll) and restore (resume at node, scroll to block); "Continue reading" entry point | 2.9, 2.8 | TODO |
| 2.11 | Meilisearch index design: one document per content block with node path, chapter title, section title, plain text, block id, book id | 0.2 | TODO |
| 2.12 | Indexing Celery tasks: full reindex command, incremental reindex on publish, delete on unpublish | 2.11, 2.4 | TODO |
| 2.13 | Search API and UI: phrase search, highlighted snippets, results grouped by chapter, click navigates to the node and scrolls to the exact block | 2.12, 2.8 | TODO |
| 2.14 | Responsive pass: desktop, laptop, tablet, mobile; keyboard navigation for TOC and prev/next, focus management, sensible contrast | 2.8 | TODO |
| 2.15 | Tests: TOC integrity, prev/next at first and last node, published-only visibility, search returns correct block, position round-trip, cross-course node access denied | 2.13, 2.10 | TODO |

---

## Stage 3: Deliverable 3 — Content Management System

| Id | Task | Depends on | Status |
|---|---|---|---|
| 3.1 | Admin authentication and `IsContentAdmin` permission; CMS routes and APIs deny everyone else | 1.1 | TODO |
| 3.2 | Book management API and UI: create, edit metadata, archive | 3.1, 2.1 | TODO |
| 3.3 | Hierarchy manager API: create, rename, move, reorder (position rebalancing), soft-delete nodes, transactional | 3.1, 2.2 | TODO |
| 3.4 | Hierarchy manager UI: tree view with drag-and-drop reorder and move, inline rename, add child, archive | 3.3 | TODO |
| 3.5 | Tiptap editor integration: headings, lists, tables, image upload, links, footnotes and references, figure node with caption and alt text, callout node; new top-level nodes get a fresh `blockId`, edits preserve it | 3.1 | TODO |
| 3.6 | Draft and publish service: saving creates or updates the working draft; publishing creates an immutable `ContentVersion` with author, timestamp and change note, marks it published, dispatches reindexing | 3.5, 2.4, 2.12 | TODO |
| 3.7 | Version history UI: version list per node, view any version read-only, side-by-side text diff, restore as a new draft | 3.6 | TODO |
| 3.8 | Affected-readers service and UI: for a node, list users with a reading position on it | 3.6, 2.9 | TODO |
| 3.9 | Preview mode: render a draft version in the real reader layout with a persistent draft banner, admin-only | 3.6, 2.8 | TODO |
| 3.10 | Media handling: image upload with validation (type, size, dimensions), storage and retrieval; alt text required | 3.5 | TODO |
| 3.11 | Import pipeline core: upload endpoint, `ImportJob` model (source file, status, log, target parent node, created_by), Celery orchestration | 3.1 | TODO |
| 3.12 | Word, HTML and EPUB conversion via Pandoc to HTML, then HTML to Tiptap JSON with heading-based node splitting and `blockId` assignment | 3.11 | TODO |
| 3.13 | PDF conversion via Poppler: `pdftohtml` for text and structure, `pdfimages` for figures, heuristic heading detection, best-effort tables, landing as a flagged draft | 3.11 | TODO |
| 3.14 | Import review UI: job status, conversion log with warnings, per-node accept or edit before publishing; nothing imported is ever auto-published | 3.12, 3.13 | TODO |
| 3.15 | Activity log: every administrative action recorded with actor, action, target, timestamp; viewable and filterable in the CMS | 3.1 | TODO |
| 3.16 | Tests: publish creates a version, prior versions immutable, restore creates a new version, blockId stability across edits, reading position survives a publish, import produces editable drafts, non-admin denied on every CMS endpoint | 3.14, 3.7 | TODO |

---

## Stage 4: Deliverable 4 — UX, Testing and Deployment

| Id | Task | Depends on | Status |
|---|---|---|---|
| 4.1 | Student home: continue reading card, TOC entry, search entry, course and book context | 2.10 | TODO |
| 4.2 | Faculty dashboard: course, linked textbook, continue reading, clearly labelled placeholders for later teaching tools | 1.12, 2.6 | TODO |
| 4.3 | Access control audit: enumerate every endpoint and route, confirm explicit permission, automated test per denial case | 3.16, 2.15 | TODO |
| 4.4 | Security hardening: CSP with `frame-ancestors` for the Canvas host, secure cookie flags, rate limiting on LTI and search endpoints, CSRF, upload validation, `pip-audit` and `npm audit` clean or documented | 4.3 | TODO |
| 4.5 | GAU branding applied: logo, palette, typography, favicon, launch and error states | 4.1, 4.2 | TODO |
| 4.6 | Responsive and accessibility QA across desktop, tablet and mobile; keyboard-only pass; contrast check | 4.5 | TODO |
| 4.7 | Full regression suite green: pytest plus Playwright covering all thirteen acceptance criteria | 4.6 | TODO |
| 4.8 | Production deployment on the Hostinger KVM VPS: Docker Compose, Nginx, HTTPS via Let's Encrypt, Gunicorn tuning, Celery worker and beat under supervision, PostgreSQL nightly dumps, media backup, Meilisearch persistence | 4.7 | TODO |
| 4.9 | Canvas LTI configuration in the agreed Canvas environment; verified production launch end to end | 4.8, 1.17 | TODO |
| 4.10 | Documentation complete: `ENVIRONMENT.md`, `CANVAS_SETUP.md`, `DEPLOYMENT.md`, `ADMIN_GUIDE.md`, `ARCHITECTURE.md` with module and service interface notes for Phase 2 | 4.9 | TODO |
| 4.11 | Acceptance testing support and bug fixing | 4.10 | TODO |

---

## Acceptance criteria coverage

Every criterion needs a passing automated test or a documented manual test before
Phase 1 is done.

| # | Criterion | Proven by |
|---|---|---|
| 1 | Canvas user launches without creating a second account | 1.16, 4.7 |
| 2 | Student and Faculty roles correctly recognised | 1.16, 4.7 |
| 3 | Correct Canvas course context received and used | 1.16, 4.7 |
| 4 | Textbook opens as structured web content, not a PDF viewer | 2.15, 4.7 |
| 5 | Book/unit/chapter/section/subsection navigation, including prev/next boundaries | 2.15, 4.7 |
| 6 | Search returns usable results and opens the relevant location | 2.15, 4.7 |
| 7 | Leave and return continues from the saved position | 2.15, 4.7 |
| 8 | Administrator can create, edit, organise, preview and publish | 3.16, 4.7 |
| 9 | Import workflow available, imported content editable before publishing | 3.16, 4.7 |
| 10 | Content updates create traceable versions, no destructive replacement | 3.16, 4.7 |
| 11 | Core screens work on desktop, tablet and mobile | 2.14, 4.6 |
| 12 | Student, Faculty and Administrator access correctly restricted, cross-course denial included | 4.3, 4.7 |
| 13 | Phase 1 environment deployed and available for testing | 4.8, 4.9 |

---

## Open questions for GAU

Recorded here as they arise so no loop guesses. None outstanding yet; the
following are known to be needed before the tasks that depend on them:

- Canvas sandbox, developer key and test accounts (Student, Teacher, Admin) in a
  test course — needed to complete **1.16** and **4.9**. Tasks 1.1–1.15 can be
  built and tested against a local mock platform.
- Confirmed chapter and unit structure for the nursing textbook, or approval to
  derive it from document headings — needed for **3.13**.
- GAU branding assets: logo, palette, typography — needed for **4.5**.
- Hosting target confirmation and the platform subdomain with DNS access —
  needed for **4.8**.
- Course-to-book mapping for the demonstration course — needed for **2.5**.
