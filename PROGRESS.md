# PROGRESS — GAU Interactive Textbook Platform, Phase 1

Task board for the build loop. One task per loop. Status values: `TODO`,
`IN PROGRESS`, `DONE`, `BLOCKED`.

A task is `DONE` only when a passing test or a verified command proved it.
A task is `BLOCKED` with the specific question recorded inline, so the next loop
does not repeat the work.

**Current status:** Stage 1 built; Stage 2 started. **0.8**, **1.1**–**1.17**,
**2.1**–**2.7** are implemented. Everything awaits a Docker test run — including the
suite itself, which is written but has never been executed.

---

## Stage 0: Foundations

| Id | Task | Depends on | Status |
|---|---|---|---|
| 0.1 | Git repo, `.gitignore`, branch strategy, PR template `[micro]` | — | **DONE** |
| 0.2 | Docker Compose: postgres, redis, meilisearch, backend, frontend, celery worker, celery beat, nginx | 0.1 | **DONE** |
| 0.3 | Django project with split settings, `.env.example` listing every variable | 0.2 | **DONE** |
| 0.4 | Next.js 14 app with TypeScript, Tailwind, path aliases, typed API client shell | 0.2 | **DONE** |
| 0.5 | pytest and Playwright configured, one smoke test each | 0.3, 0.4 | **DONE** |
| 0.6 | GitHub Actions: ruff, mypy, pytest, eslint, tsc, next build | 0.5 | **DONE** |
| 0.7 | `docs/ARCHITECTURE.md` and `docs/ENVIRONMENT.md` first draft | 0.3 | **DONE** |
| 0.8 | Align the backend with the agreed layout: `core/`, central migrations, module directories | 0.7 | **IN PROGRESS** |

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

- pytest pins its own settings with `--ds=core.settings.test` in `addopts`
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

**0.6 notes —** `.github/workflows/ci.yml` with three jobs: `backend`
(ruff lint, ruff format, mypy strict, pytest with coverage, against postgres and
redis service containers), `frontend` (eslint, tsc, production build), and `e2e`
(needs both; brings the real stack up and runs Playwright, uploading the report
as an artefact).

ruff and mypy ran for the first time here and found 11 issues, all fixed. The
whole compose stack also came up for the first time — 8/8 services healthy.

**The workflow itself has not run on GitHub.** `gh` auth on this machine is
broken (keyring), so no Actions run could be triggered. Every gate was executed
locally under CI-identical invocations and the YAML was parsed and its job graph
checked, but *that the workflow triggers and passes on GitHub is unverified
until the branch is pushed.* First push should confirm it before 0.7 is
accepted as safe to build on.

Points the next loops must respect:

- **Migrations are no longer run on container start** (D-020). A fresh
  environment needs `docker compose run --rm backend python manage.py migrate`.
  Task 1.1 runs it for the first time — and must confirm `django_migrations` is
  empty beforehand, which it still is (verified: 0 tables in `public`).
- **`docker compose up` is not what CI runs** (D-021). It loads
  `docker-compose.override.yml` and gives the Next dev server. CI uses
  `docker compose -f docker-compose.yml up`, the production build. Anything
  asserting on timing or built output must use the latter.
- mypy needs the application environment because its Django plugin imports the
  settings module. A missing variable surfaces as a plugin crash, not a type
  error. The CI job sets throwaway values for exactly this reason.
- The `backend` CI job has **no meilisearch service** — nothing tests against it
  yet. Task **2.12** must add one when indexing tests land, or they will fail
  with a connection error rather than an assertion.
- `core.celery` is the one module with `no-untyped-call` disabled, because
  Celery ships no type information. Verified not to leak: the same call in
  another module still errors.

**0.7 notes —** `docs/ARCHITECTURE.md` covers the system, request paths
(page load and Canvas launch), module boundaries, the ten architecture rules
each paired with the failure it prevents, the content model, frontend, background
work, testing and later-phase attachment points. `docs/ENVIRONMENT.md` documents
all 42 variables with defaults and consequences. Anything not yet built is marked
with the task that builds it. A root `README.md` points at both.

`scripts/check_env_docs.py` compares what the settings, Compose and the frontend
read against `.env.example` and fails on drift; it is now a step in the backend
CI job. Verified at 42 read, 42 declared, no drift.

Writing ENVIRONMENT.md surfaced a real defect from 0.3: `DATA_UPLOAD_MAX_MEMORY_SIZE`
had been raised to 64 MB to allow large document imports, but that setting
excludes file uploads entirely. It enabled nothing and widened a DoS surface for
JSON bodies. Corrected to 10 MB (D-022).

**Owed when Docker testing resumes — run these first:**

Docker is paused at the user's request, so the following change is verified only
at host level (AST parse and default value extraction), not by the suite:

- `backend/core/settings/base.py` — `DATA_UPLOAD_MAX_MEMORY_SIZE` default
  64 MB → 10 MB. Run `ruff check`, `ruff format --check`, `mypy .` and `pytest`
  in the backend image. Low risk (an integer default no test asserts on), but
  unverified by the toolchain.
- `.github/workflows/ci.yml` — new `.env.example matches the code` step. YAML
  re-parsed with host Ruby; still never run on GitHub (see 0.6).

Points the next loops must respect:

- **Task 3.10 and 3.11 must enforce upload size in validation.** Neither Django
  upload setting limits a file's size, and the settings file will tempt a reader
  to assume otherwise (D-022).
- Adding or removing a setting now fails CI unless `.env.example` changes in the
  same commit. Update `docs/ENVIRONMENT.md` alongside it.
- ARCHITECTURE.md marks module status explicitly. When a task builds a module,
  update its row from a task number to built — a doc claiming something is
  "task 2.1" after it ships is as misleading as one claiming it is built before.

---

## Stage 1: Deliverable 1 — Canvas LMS Integration

| Id | Task | Depends on | Status |
|---|---|---|---|
| 1.1 | `accounts.User` model: uuid pk, canvas_user_id unique, name, email, avatar_url, is_content_admin | 0.3 | **IN PROGRESS** |
| 1.2 | `lti.LtiPlatform` model: issuer, client_id, deployment_ids, auth_login_url, auth_token_url, jwks_url, tool private key reference — from env or fixtures, never hard-coded | 0.3 | **IN PROGRESS** |
| 1.3 | Tool RSA keypair generation management command plus public JWKS endpoint `/lti/jwks/` | 1.2 | **IN PROGRESS** |
| 1.4 | OIDC login initiation `/lti/login/`: state and nonce generation, stored in Redis with TTL, redirect to Canvas auth URL | 1.3 | **IN PROGRESS** |
| 1.5 | Launch endpoint `/lti/launch/`: PyLTI1p3 validation of signature, issuer, aud, nonce replay, exp/iat, deployment id; clear error page on any failure | 1.4 | **IN PROGRESS** |
| 1.6 | `courses.Course` and `courses.CourseMembership` models keyed on Canvas ids | 1.1 | **IN PROGRESS** |
| 1.7 | Role normalisation service: LTI role URIs to `STUDENT`, `FACULTY`, `ADMIN`; unknown roles default to lowest privilege | 1.6 | **IN PROGRESS** |
| 1.8 | Launch provisioning service: upsert user, course and membership from launch claims in one transaction; first launch creates the user, never a second account | 1.5, 1.7 | **IN PROGRESS** |
| 1.9 | Session establishment for iframe context: signed session cookie `SameSite=None; Secure; HttpOnly`, short-lived launch token handed to the frontend | 1.8 | **IN PROGRESS** |
| 1.10 | New-window launch fallback for browsers blocking third-party cookies, with an "open textbook" interstitial | 1.9 | **IN PROGRESS** |
| 1.11 | `CourseScoped` permission and middleware: every request carries the launch course context; 403 on any other course | 1.9 | **IN PROGRESS** |
| 1.12 | Role routing on the frontend `/launch` page: student to reader, faculty to dashboard, admin offered CMS | 1.9 | **IN PROGRESS** |
| 1.13 | NRPS roster sync Celery task: fetch memberships, reconcile additions and removals, scheduled and on-demand | 1.8 | **IN PROGRESS** |
| 1.14 | Deep Linking request and response handler (foundation): accept a deep link request, return a content item pointing at a node UUID | 1.5 | **IN PROGRESS** |
| 1.15 | `lti.LtiLaunchLog` audit model: nonce, user, course, role, timestamp, outcome | 1.5 | **IN PROGRESS** |
| 1.16 | Tests: valid launch, expired token, wrong aud, replayed nonce, unknown role, cross-course 403, first-launch provisioning, repeat-launch idempotency | 1.11 | **IN PROGRESS** |
| 1.17 | `docs/CANVAS_SETUP.md` plus the tool JSON configuration for the Canvas admin | 1.5 | **IN PROGRESS** |

**1.1 notes: implemented but not verified.** `apps/accounts` provides
the User model (UUID pk, unique `canvas_user_id`, unusable reader passwords), a
manager, and a Django admin that cannot add users and shows Canvas-supplied
fields read-only (D-023). `AUTH_USER_MODEL` and `apps.accounts` are now set in
the same change as `0001_initial` (D-009). The 0.5 guard test has been replaced
by its successor as planned.

`0001_initial.py` was **written by hand** because Docker is paused. It was
checked against the Django 5.2 source (fetched through the GitHub API) and
statically compared with the model: 15 of 15 fields match.

**Owed before 1.1 can be marked DONE, in this order:**

1. Confirm `django_migrations` does not exist or is empty in the dev database (D-009).
2. `python manage.py makemigrations --check --dry-run` — must report no changes.
   If it does, regenerate `0001_initial` rather than patching it.
3. `docker compose run --rm backend python manage.py migrate`
4. `ruff check`, `ruff format --check`, `mypy .`
5. `pytest`: 36 existing tests plus the new ones in `tests/test_accounts.py`,
   including `test_models_and_migrations_are_in_sync`.
6. Commit only once these pass. Do not stage `docs/` or `screenshots/`.

**1.2 notes: implemented and host-verified.** `apps/lti` holds the
`LtiPlatform` model, its `services.py` interface and one management command.
Registrations come from a JSON file named by `LTI_PLATFORMS_FILE` (D-025), so no
Canvas host, client id or deployment id appears in code — verified by search.
The file is gitignored: it names a specific institution's Canvas.

`services.py` is the only way other modules reach a registration (rule C.1).
`resolve_launch(issuer, client_id, deployment_id)` checks all three claims
together and is what tasks 1.4 and 1.5 call; `get_platform` never returns an
inactive registration, so a retired developer key cannot be accepted by a code
path that forgot to check.

`migrations/lti/0001_initial.py` was **written by hand** because Docker is
paused, and statically compared with the model: 11 of 11 fields match, the four
Meta options match, and the validator is fully qualified as Django's serialiser
emits it.

**No tests were written for 1.2, at the client's direction.** Task **1.16**
owes the coverage: unknown issuer refused, inactive registration refused,
unregistered deployment id refused, sync idempotent, sync never deleting,
malformed configuration rejected before it is stored.

**Owed before 1.2 can be marked DONE, in this order:**

1. `manage.py makemigrations --check --dry-run` — no changes expected. If there
   are, regenerate `migrations/lti/0001_initial.py` rather than patching it.
2. `manage.py migrate`, then `mypy .` and `pytest`.
3. `manage.py sync_lti_platforms --dry-run --file <a registration file>` against
   a real database, then without `--dry-run`, then a second time to prove it
   reports everything unchanged.

**Found while verifying 1.2, and fixed:** `ruff check` had never run against
task 1.1's code, because ruff lives in the backend image and Docker is paused.
Run from the host it reported **RUF012** on `apps/accounts/models.py:54`
(`REQUIRED_FIELDS`) — a lint failure that would have broken the backend CI job
on first push. Both that and the same issue in the new model are now annotated
`ClassVar`. Host ruff is 0.15.4; the image resolves `ruff>=0.6,<1.0` at build
time, so the versions may differ and the image run is still owed.

**1.16 notes: written, NOT RUN.** The client lifted the no-tests instruction,
so Stage 1's coverage now exists: **109 test functions** across the suite, of
which 64 are new here, and several are parametrised into more cases than that.

| File | Covers |
|---|---|
| `test_lti_claims.py` | reading a verified launch; role normalisation |
| `test_provisioning.py` | first launch, repeat launch, idempotency, role changes |
| `test_lti_scope.py` | the course scope, and cross-course refusal |
| `test_lti_registration.py` | platform registration, tool keys, replayed nonce |

**They have never been executed.** Docker is paused at the client's request and
Django is not installed on the host, so not one assertion has run. What has been
checked is weaker and should be read as such: ruff is clean, every file parses,
and all **68 names the tests import were confirmed to exist** in the modules
they are imported from — which catches a renamed function but not a wrong
expectation.

Several of these assert behaviour I had already executed standalone while
building the tasks (role normalisation, claim parsing, object scoping, the
thumbprint), so those are likely to pass. The database-backed ones are not
verified in any sense.

**Deliberately not covered, and why.** "Expired token" and "wrong aud" as
*end-to-end signed JWTs* are not here. They need a mock platform issuing real
tokens against a JWKS the tool will fetch, and writing that blind — against
PyLTI1p3 internals I cannot execute — would produce tests that fail for their
own reasons rather than the code's. What *is* covered is our half: a wrong
audience does not resolve to a registration, an uninstalled deployment is
refused, and the nonce is single-use at the layer that implements it. The
end-to-end JWT tests are owed when Docker returns.

**Owed before 1.16 can be marked DONE:**

1. `pytest` — expect failures on first run; tests written blind usually have
   some. The cost of fixing them is the price of not having run them earlier.
2. Confirm the four `test_lti_*` files reach the database and the cache aliases
   resolve (D-039 fixed `test.py` for exactly this).
3. Add the end-to-end launch tests against a mock platform: expired `exp`,
   wrong `aud`, replayed nonce through the real `/lti/launch/` endpoint.
4. Wire coverage into CI and set a floor.

**1.17 notes: implemented and host-checked; docs on disk, not staged.**
`manage.py lti_tool_config` emits the Canvas developer key JSON, and
`docs/CANVAS_SETUP.md` is the administrator's guide.

**The JSON is generated, not written down.** Every URL derives from
`PLATFORM_BASE_URL`, so the output is always right for the environment it was
produced on. A configuration copied out of documentation is one that silently
points at staging after someone forgets a line — and the symptom is a launch
failing validation for no visible reason.

Rendered on this host and checked: all three URLs derive from the base, the
only scope requested is Names and Roles read-only (**no grade scopes** — the
platform does not assess, and a scope granted for nothing is still a
permission), and both deep linking placements are present.

The guide is written for GAU's Canvas administrator, marks the operator's steps
separately, and ends with a table mapping what a student sees to where the fix
is — which is what the launch log from 1.15 makes answerable.

`privacy_level` is surfaced as **GAU's decision, not a technical one**: the
textbook works at every level, including `anonymous`.

**Owed before 1.17 can be marked DONE:**

1. Run `manage.py lti_tool_config` for real and paste the output into a Canvas
   developer key — **needs GAU's Canvas**.
2. Walk the guide end to end with the Canvas administrator, as a student and
   as a teacher. That is acceptance criteria 1, 2 and 3 demonstrated manually,
   and until 1.16 exists it is the only demonstration there is.

**1.15 notes: implemented and host-checked.**
`lti.LtiLaunchLog` records every launch; `apps/lti/audit.py` writes it; the
launch view records all six outcomes — accepted, deep link, and four distinct
refusals.

**No foreign keys, deliberately** (D-051). The user and course are plain UUID
columns. An audit record must outlive what it describes, must never be the
reason another operation fails, and most refused launches have no user or
course to point at anyway.

**Writing the record can never break a launch.** Every failure is logged and
swallowed — letting one propagate would trade the thing being protected for the
record of it. `claims_of` was **executed on this host** against a full launch
body, a string `aud`, an empty `aud`, a non-dict body, a launch that throws and
`None`: six for six return something usable rather than raising on the failure
path, which is the only path it runs on.

Model and migration compared field by field: 12 of 12 match, including the six
outcome choices and both indexes.

**Owed before 1.15 can be marked DONE:**

1. `makemigrations --check`, `migrate`, `ruff`, `mypy .`, `pytest`.
2. Each of the six outcomes produces exactly one row with the right fields.
3. A replayed launch produces two rows sharing a nonce, the second refused.
4. Confirm no name, email or token reaches any column.

**Points the next loops must respect:**

- **Task 4.8** must agree a retention period with GAU and add pruning. The
  table grows without bound, and an audit log nobody can query is no better
  than none.
- **Task 4.3**'s access-control audit can use this table as evidence rather
  than reasoning from the code alone.

**1.14 notes: implemented and host-checked.**
`apps/lti/deep_linking.py` answers a Deep Linking request with a signed content
item; the launch view branches to it before provisioning; the node id it
carries comes back on the resulting launch and is passed through to
`/launch?node=…` and on to the destination.

**The content item points at `/lti/launch/`, never at a chapter URL** (D-050). A
URL pointing straight at content would bypass the signature, nonce, deployment
and course-scope checks that 1.5–1.11 exist to provide. Going through the
launch endpoint makes a deep-linked chapter exactly as protected as any other,
and turns the node id into a preference expressed inside a verified launch
rather than an access decision made by a URL.

Answered **before** provisioning, because a deep linking request is someone
building a course and does not always carry a course context; requiring one
would refuse a legitimate account-level request.

The foundation returns one item for the whole textbook — choosing a chapter
needs chapters. What is working now is the part that would otherwise be found
late: the custom parameter, the claim carrying it back, and the route from that
claim to the reader.

The `apps/lti` import graph was checked for cycles after adding the module:
`keys`, `deep_linking` and `middleware` are leaves, `services` depends on them,
`tool_conf` on `services`, and `views` on everything. No cycles.

**Owed before 1.14 can be marked DONE:**

1. `migrate`, `ruff`, `mypy .`, `pytest`, `tsc`, `eslint`.
2. A real deep linking request from Canvas returns an item Canvas accepts —
   **needs GAU's Canvas**, and needs a tool key assigned, since the response is
   signed. This is where D-027's `kid` fix is first exercised for real.
3. Launching the resource link Canvas created arrives with the `custom` claim
   and lands on `/launch?node=…`.

**Points the next loops must respect:**

- **Task 2.8** must honour `?node=` in the reader.
- **Task 2.5** should replace the constant item title with the book's own.
- The picker belongs with **2.2/2.3**; the plumbing it needs is already here.

**1.13 notes: implemented and host-checked.** `services/roster.py`
reconciles a course against the Canvas roster; `apps/lti/tasks.py` runs it on
demand and every six hours on the `canvas` queue. `Course` gained the Names and
Roles URL and a `roster_synced_at`, and `migrations/courses/0001_initial.py` was
amended — safe only because nothing has ever been applied (D-009).

**The dangerous case is a course with no Names and Roles URL** (D-049). "No
service" and "an empty roster" are indistinguishable from here, and treating one
as the other would deactivate an entire course. Those courses are skipped.

The member interpretation was **executed on this host** against realistic NRPS
payloads: a normal learner and a member with no `status` are kept active, a
`Deleted` or `Inactive` enrolment is deactivated, a member with no `user_id` is
skipped rather than crashing the run, and a `roles` value that is not a list
degrades to no roles rather than throwing.

Nothing is deleted — departure is `is_active = False`, because a reading
position hangs from the membership.

**The network call is outside the transaction**, so a slow roster does not hold
locks on every row in the course.

**Owed before 1.13 can be marked DONE:**

1. `makemigrations --check`, `migrate`, `ruff`, `mypy .`, `pytest`.
2. A real NRPS fetch against a Canvas sandbox with the scope granted —
   **this is the first task that needs GAU's Canvas**, since it signs a client
   assertion and exchanges it for a token.
3. A member removed in Canvas becomes inactive on the next sync, and their
   reading position survives it.
4. A course with no NRPS URL is skipped and its memberships are untouched.
5. Beat actually fires `sync_all_rosters` on the configured interval.

**Points the next loops must respect:**

- **`ROSTER_SYNC_INTERVAL_SECONDS` is a security parameter**, not a performance
  one: it is how long a student removed from a Canvas course keeps access.
  Raise the six-hour default with GAU at **4.9**.
- **Task 2.9** must not add a cascade from `CourseMembership` to
  `ReadingPosition`. Deactivation is the removal mechanism precisely so the
  position survives.
- The mypy relaxation for Celery now covers `apps.*.tasks` as well as
  `core.celery`. **Task 2.12 and 3.11** add task modules and inherit it;
  business logic stays strict.

**1.12 notes: implemented and host-checked.** `/launch` is the
frontend landing a verified launch now redirects to. It resolves the session,
redeems a launch ticket if the cookie did not survive, removes the ticket from
the address bar, and shows the role-appropriate way on.

**The launch ticket's fate is settled: it stays** (D-045, closing D-042). It now
has a caller — the landing page falls back to it only when
`GET /lti/context/` says there is no session — so it is no longer the dead
credential-issuing endpoint D-042 was worried about, and it recovers silently
from the cookie policies that differ between browsers.

`destinationFor` was **executed on this host** across all three roles: a student
has exactly one way on, faculty land on their dashboard with the textbook
offered alongside, and an administrator is **offered** the CMS rather than sent
to it. That wording in the backlog is load-bearing, and the route is a
convenience rather than a gate — entry to the CMS is decided by
`is_content_admin` on the server, which no Canvas role confers (D-023, D-046).

`tsc --noEmit` and `eslint` both clean on the new files.

**Review findings, all four fixed (D-047).** Every one was in the fallback path
— the branch that only runs when the session cookie was discarded, and so the
one least likely to be caught before a student hits it. Two of them destroyed
the ticket recovery D-045 exists for: the ticket was stripped from the URL
before the abort check, and a redemption whose body failed validation was read
as "no session" even though the browser had honoured its `Set-Cookie`. Also
fixed: `replaceState(null, …)` was erasing the App Router's history state on
every launch, and an unmounted component could burn the single-use ticket.

The review confirmed the contracts line up end to end: role values, the
`course_id`/`role` key names on the redemption response, `LANDING_PATH` against
the route, the `lt` parameter, and that the POST carries only `Accept` and
`X-Launch-Ticket` with `credentials: 'include'` so the cookie is stored. It also
confirmed the origin guard cannot 403 every redemption on a trailing slash,
since `PLATFORM_BASE_URL` is normalised.

One of its open questions is answered: `name` and `email` on the user model are
`CharField`/`EmailField` with `blank=True` and no `null=True`, so they arrive as
`""` rather than null, and the guard will not reject a user without an email.

**Owed before 1.12 can be marked DONE:**

1. `npm run build`, `eslint`, `tsc` in CI; `pytest` and `mypy .` on the backend.
2. A real launch lands on `/launch`, resolves the context and shows the right
   destination for each of the three roles.
3. With the session cookie blocked, the ticket path recovers and the address
   bar no longer contains `lt` afterwards.
4. A direct visit to `/launch` with no session shows the "open it from Canvas"
   message rather than an error.

**Points the next loops must respect:**

- `/reader`, `/faculty` and `/cms` do not exist yet (tasks 2.8, 4.2, 3.2). The
  page **presents** the destination rather than redirecting, because sending
  someone straight to a page that does not exist is worse than showing them
  where they are. **Task 2.8** can switch student and faculty to an automatic
  redirect once the reader is real.
- **Tasks 4.1 and 4.2** must reuse `lib/launch/routing.ts` rather than restate
  the rule.

**1.11 notes: implemented and host-checked.**
`apps/lti/middleware.py` puts the launch's course and role on every request;
`apps/lti/permissions.py` enforces them; `GET /lti/context/` is the first
consumer and is what task 1.12 will route on.

**The scope is read from the session, never from the request** (D-043). A course
id in a URL is a request; a course id in the session is a fact a signed launch
established. `LaunchContextView` takes no course parameter at all, so there is
nothing to tamper with.

`has_object_permission` was **executed on this host** — **8 of 8** cases behave
as intended. A Course, a membership, and a membership whose relation is deferred
all resolve; a book, a null course foreign key, a bare string, None, and a
foreign class that merely calls itself `Course` are all denied.

**Review findings, addressed (D-044).** Course identity is now an `isinstance`
rather than a class-name comparison, which was correct only while one class in
the process is called Course. A fallback branch reading `obj.course` was dead —
any Django foreign key named `course` also exposes `course_id`, consumed first —
and is gone. An earlier version of this note claimed a "related via `.course`"
model shape was covered; that leg of the hand-check was exercising a synthetic
object, and the claim was wrong.

**What the review could not close:** `has_object_permission`, the half that
actually produces "403 on any other course", has no caller until task 2.6. The
mechanism is sound and fails closed, but **nothing in the system can emit a
cross-course 403 yet**, so acceptance criterion 12 is not demonstrated by
anything. That is the backlog's ordering, not a defect here — but it means 12
rests on 2.6, 1.16 and 4.3, and on nothing before them.

The bypass hunt found nothing: an admin-login session gets no scope because it
is the course key that gates it; the session keys have two writers, both
post-verification; the scope attribute is overwritten on every request so it
cannot be pre-seeded; and both sides of the id comparison are `str(uuid.UUID)`,
so there is no formatting mismatch and no possible collision.

**No tests, at the client's direction.** Task **1.16** owes the cross-course 403
in particular — it is acceptance criterion 12 and currently rests on a hand-run
check of one helper.

**Owed before 1.11 can be marked DONE:**

1. `migrate`, then `ruff check`, `ruff format --check`, `mypy .`, `pytest`.
2. `GET /lti/context/` returns the launch's course for a launched session, and
   403 for a session that never launched.
3. An object from another course is refused through `check_object_permissions`.
4. Confirm an anonymous request gets no scope, even with a stale session cookie.

**Points the next loops must respect:**

- **Task 2.6 must filter its querysets by the scope.** `has_object_permission`
  only runs when a view calls `check_object_permissions`, so a list endpoint
  that returns rows without per-object checks is not protected by this class.
  That is the likeliest way criterion 12 gets broken later.
- **Task 2.2**'s `ContentNode` belongs to a book, not a course, so it cannot be
  guarded directly; 2.6 resolves book to course and scopes there.
- **Task 1.12** consumes `GET /lti/context/` and decides the fate of the launch
  ticket (D-042).

**1.10 notes: implemented and host-checked.** `/lti/login/` now
calls `enable_check_cookies()` with our own wording (D-041), so a launch first
renders a page that writes a cookie and reads it back, and offers a new tab when
that fails.

**This turned out to be load-bearing, not a nicety.** The 1.9 review established
that PyLTI1p3 binds the OIDC `state` to a cookie on a first launch, so a browser
blocking third-party cookies fails *at launch* — and reports itself as a
verification failure, which reads like a misconfigured developer key. Without
1.10, Safari's defaults would have looked like a broken Canvas registration.

No new interstitial was built: D-029 recorded that the library ships one, and
building a second mechanism would have meant maintaining our own copy of a
security-relevant handshake step.

**The launch ticket is kept, and its fate is task 1.12's to settle** (D-042).
D-040 asked whether it survives; on the evidence it is not needed, because the
new-tab flow gets a session cookie directly. It stays because the backlog
specifies it and narrowing agreed scope is not a call to make unilaterally —
but `POST /lti/session/`, `redeem_launch_ticket` and `RedeemedSession` have no
caller until 1.12, which is a real tension with Section H.

**Review verdict: complete.** No code defects. It confirmed the parts that
could have gone wrong: the interstitial is a real `HttpResponse`, so
`canvas_framable` stamps `frame-ancestors` on it; the new tab is a genuine
`window.open(..., '_blank')` from a user gesture, so popup blockers allow it;
`lti1p3_new_window=1` makes the second pass skip the check, so no loop is
possible; no state or nonce is written until the second pass, so sitting on the
interstitial cannot expire the 600-second window; and the platform parameters
are escaped before being embedded, so the unauthenticated endpoint carries no
XSS.

Three documentation defects, all fixed in D-041: without JavaScript the reader
gets a **blank page**, not a loading message; issuer validation now happens one
round trip later, which was unrecorded; and a browser blocking cookies outright
still ends on the misleading "could not be verified" page, which is the
library's design rather than something 1.10 fixes.

**Owed before 1.10 can be marked DONE:**

1. `migrate`, then `ruff check`, `ruff format --check`, `mypy .`, `pytest`.
2. A launch in a browser that allows third-party cookies: the check page
   appears and continues on its own, and the session cookie is set.
3. A launch in Safari, or Chrome with third-party cookies blocked: the
   interstitial offers a new tab, and the launch completes in it.
4. Confirm the interstitial carries `Content-Security-Policy: frame-ancestors`
   — unlike the 302, this is a real document and the header is enforced.

**Points the next loops must respect:**

- **Task 4.5** must decide whether to restyle the interstitial. It is the
  library's markup, carries no GAU branding, and some readers will see it
  before anything else.
- **Task 1.12** decides whether the launch ticket lives. If the frontend has no
  use for it, remove the endpoint rather than ship an unused credential-issuing
  route.
- **Task 1.16** must cover a blocked-cookie launch, not only the happy path.
  It is the case most likely to reach a real student.

**1.9 notes: implemented, reviewed, host-checked only.** A verified launch
now signs the user in and redirects to the frontend with a launch ticket.

`services/launch_session.py` owns both ways in: the session cookie, and the
ticket for when that cookie is discarded. `POST /lti/session/` exchanges a
ticket. The ticket **must** arrive in the `X-Launch-Ticket` header — that is
what makes exempting the endpoint from CSRF safe (D-038), since a cross-site
form cannot set a custom header.

**Cookie flags moved from `prod.py` to `base.py`** (D-037). They were only
being exercised in production, and `dev.py` was actively relaxing
`SESSION_COOKIE_SECURE`, which would have broken the iframe session locally —
`SameSite=None` is rejected without `Secure`. The failure mode is silent: the
launch works and every request after it is anonymous.

The launch response is now a redirect rather than the interim "Launch verified"
page. That page was scaffolding; the redirect is the real shape, and the
frontend route it lands on exists.

**Review findings, all addressed (D-039, D-040).** Two mattered:

- **The test settings defined only the `default` cache alias**, so every test
  1.9 owes — mint a ticket, redeem it, refuse the second redemption, refuse a
  POST without the header — would have raised `InvalidCacheBackendError` on
  setup and read as a broken test rather than broken settings. 1.9's central
  claim was untestable as configured.
- **Sessions were stored in the page cache.** Clearing a stale page would have
  signed every reader out mid-chapter, and LRU eviction could drop a session at
  any time. Sessions now have their own Redis database (D-039).

Also: `SESSION_LAUNCH_KEY` was dead and is gone; the `lti_state` alias is named
once in settings; and an `Origin` check backs up the header requirement on
`/lti/session/`.

**Not fixed, with an owner:** the Next.js landing page carries no
`frame-ancestors` policy now that the launch ends in a redirect. Task 4.4 owns
it, and D-040 records why the obvious `next.config.mjs` fix is wrong.

**Open for 1.10:** PyLTI1p3 binds `state` to a cookie on a first launch, so a
browser blocking third-party cookies fails *at launch*, before a ticket exists.
1.10 must decide whether the ticket mechanism survives that, and remove it if
not.

**Owed before 1.9 can be marked DONE:**

1. `migrate`, then `ruff check`, `ruff format --check`, `mypy .`, `pytest`.
2. Inspect the `Set-Cookie` on a real launch: `SameSite=None`, `Secure`,
   `HttpOnly`, name `gau_session`.
3. A launch redirects to the frontend with `?lt=`, and that ticket redeems
   once at `POST /lti/session/` with the header and is refused the second time.
4. The same POST without the `X-Launch-Ticket` header is refused.
5. Confirm the ticket key is gone from Redis database 3 after redemption.
6. Confirm sessions land in Redis database 4, and that flushing database 0
   leaves a logged-in reader logged in.

**Points the next loops must respect:**

- **Task 1.10** opens the first-party window and posts the ticket. The
  mechanism exists; 1.10 is the interstitial and the detection of a dropped
  cookie.
- **Task 1.11** reads `SESSION_COURSE_KEY` and `SESSION_ROLE_KEY` from
  `services/launch_session.py`. It must not re-spell those strings.
- **Task 1.12** must strip `?lt=` from the address bar once redeemed, so a
  used ticket does not sit in browser history.
- Local development must use `http://localhost`, `http://127.0.0.1` or HTTPS.
  A LAN address silently drops the session cookie.

**1.8 notes: implemented and host-verified.**
`services/provisioning.py` upserts the user, course and membership in one
transaction and returns a `LaunchContext`. `/lti/launch/` now calls it, so a
verified launch produces real rows and the page names the course and role from
the database rather than from the raw claims.

New surface: `apps/accounts/services.py` (`upsert_user`), three more functions
in `apps/courses/services.py`, `parse_launch_claims` in `apps/lti/services.py`,
and the shared `backend/services/` package D-024 promised (D-033).

Module boundaries hold: `services/provisioning.py` is the only file that
crosses modules, and it does so through each module's `services.py`. A search
for one app importing another's models returns nothing.

`parse_launch_claims` was **executed on this host** against realistic Canvas
payloads — **11 of 11 cases** behave as intended. It refuses a launch missing
`iss`, `sub` or `context.id`, including when `sub` arrives as a number or the
context claim is a string rather than an object, and it degrades rather than
failing when privacy hides the name and email, when `tool_platform` is absent,
and when `roles` is not a list.

**Owed before 1.8 can be marked DONE:**

1. `manage.py makemigrations --check --dry-run`, `migrate`, then `ruff check`,
   `ruff format --check`, `mypy .`, `pytest`.
2. A real launch against a mock platform creating exactly one user, one course
   and one membership; the same launch repeated creating none of them.
3. Two simultaneous first launches for the same person producing one account,
   which is the concurrency path the savepoints exist for.

**Points the next loops must respect:**

- **Task 1.9** starts from the `LaunchContext` this returns. Establishing a
  session is not provisioning's job and must not move into it.
- **Task 1.15** should record the launch outcome around `provision_launch`,
  not inside it — provisioning must not depend on the audit model.
- **Task 1.13**'s roster sync must reuse `upsert_membership` and its
  deactivation rule rather than writing its own, or the two will drift on what
  "left the course" means.
- The reviews owed for **1.5**, **1.7** and **1.8** are outstanding; 1.5's
  agent died on a session limit and the others have not been run.

**Review of 1.5, 1.7 and 1.8 — findings and fixes (D-036).** Nine confirmed,
all addressed:

1. An unexpected exception in either LTI view escaped `canvas_framable`, so
   Django's 500 was stamped `X-Frame-Options: DENY` and the student saw a blank
   Canvas frame. Both views are now guards that cannot raise. This was a direct
   failure of 1.5's "clear error page on any failure".
2. `tool_conf()` ran a database query outside the `try`, with the same result.
3. The concurrency fix was correct only under READ COMMITTED, which nothing
   pinned — it was whatever the server or a pooler defaulted to. Now pinned.
4. `IntegrityError` was caught bare, so a foreign key violation routed into the
   unique-constraint re-read and surfaced as `DoesNotExist`. The original error
   is now re-raised when the re-read finds nothing.
5. `institution/person#Staff` granted FACULTY to non-teaching institutional
   employees. Now STUDENT.
6. `provision_launch`'s docstring claimed no privilege is inferred from a
   launch; the course role is. Narrowed.
7. A deployment the tool was never installed into reported itself as a failed
   verification. It now says what it is.
8. D-032's "confirm before 1.8" on user identity scope had never been closed —
   now settled in D-035.
9. Stale text in this file: a `LAUNCH_PATH` symbol that no longer exists, an
   `X_FRAME_OPTIONS` note contradicted by D-031, and the `iat` claim above.

`backend/utils/` now exists, holding `create_or_reread` — the first thing
general enough to belong there (D-024).

**Still unverified by the review:** the PyLTI1p3 internals D-030 rests on. The
reviewer could not repeat that audit with the library uninstalled. If
`check_value` ever gains a second call site, state validation would start
consuming state.

**1.6 notes: implemented, host-verified and reviewed.**
`courses.Course` and `courses.CourseMembership`, both UUID-keyed, plus the
`Role` enum that task 1.7 maps onto. Model and migration were compared field by
field: 16 fields across both models, both Meta blocks and both constraints agree.

**The review found the identity key unsafe and it has been changed** (D-032).
The first version keyed a course on `(issuer, canvas_course_id)`, reasoning that
a Canvas course id is unique within its Canvas. It is not: every
Instructure-hosted Canvas presents the same `iss`, so two institutions' courses
would have merged onto one row — one roster, one set of reading positions. The
key now includes `platform_guid` from the `tool_platform` claim.

Two smaller review findings fixed: `CourseMembership.ordering` was not a total
order, so pagination over rows written in one transaction — which is how task
1.8 creates them — would have been nondeterministic; and the identity comment
argued from a scenario the reviewer believed impossible (it is possible, since
D-029 taught the tool to resolve multi-client issuers, but the comment was
rewritten anyway).

Nothing is deleted here. A member who leaves the Canvas roster is deactivated
(task 1.13), because a reading position hangs from the membership. Both foreign
keys are `PROTECT` so that a stray delete fails loudly rather than quietly
taking someone's reading history.

**1.7 notes: implemented and host-verified.**
`apps/courses/services.py` — the module's public interface — maps the LTI roles
claim onto `STUDENT`, `FACULTY`, `ADMIN`. The mapping table is the IMS LIS and
LTI vocabularies, listed in both full-URI and bare-term spellings.

Deliberately **not configurable**: a deployment able to redefine which Canvas
role becomes an administrator is a privilege escalation waiting to be
misconfigured.

The logic was executed on this host against a stand-in for the Django enum, so
the shipped table and precedence rules were the ones tested — **16 of 16 cases
pass**, including: no claim, empty list, unknown-role-only, a non-string in the
list, a teacher also enrolled as a student (resolves FACULTY), an administrator
also a learner (ADMIN), the teaching-assistant sub-role URI, and Canvas's
observer role (`Mentor`), which resolves to STUDENT rather than faculty.
Every input that is not recognised yields the least privileged role.

**No tests for either task, at the client's direction.** Task **1.16** owes:
role precedence, unknown-role default, membership uniqueness, course identity
across two platform guids, and that deactivation never deletes.

**Owed before 1.6 and 1.7 can be marked DONE:**

1. `manage.py makemigrations --check --dry-run` — no changes expected.
2. `manage.py migrate`, then `ruff check`, `ruff format --check`, `mypy .`,
   `pytest`.
3. Confirm the two unique constraints exist in PostgreSQL and that inserting a
   duplicate membership raises.

**Points the next loops must respect:**

- **Task 1.8 must read `tool_platform.guid`** from the launch claims and set
  `Course.platform_guid`. A course created without it and updated with it later
  would be created twice.
- **Task 1.8** also needs `apps.courses.services.normalise_role`, reached
  through services.py and never by importing `courses.models` (rule C.1).
- **Confirm before 1.8:** `accounts.User.canvas_user_id` is unique with no
  issuer scope, while a course is scoped by platform. Canvas issues a UUID for
  `sub` so a collision is vanishingly unlikely, but the two models apply
  different identity rules inside one transaction (D-032).
- **Task 1.12** routes on the membership role; actual CMS access still requires
  `is_content_admin`, which no Canvas role confers (D-023).

**1.5 notes: implemented and host-verified.** `/lti/launch/`
validates through PyLTI1p3 and renders `lti/message.html` on every outcome.
Where each required check happens:

| Check | Performed by |
|---|---|
| `state` matches the one we issued | `MessageLaunch.validate_state` |
| nonce issued by us, and unused | `validate_nonce`, made single-use here (D-030) |
| issuer and audience resolve | `validate_registration`, comparing `aud` to the registration |
| signature | `validate_jwt_signature` against the platform's JWKS |
| `exp` | PyJWT defaults, during signature verification |
| deployment id | `validate_deployment` → `PlatformToolConf.find_deployment` |

**`iat` is not enforced as a freshness check.** PyJWT verifies `exp` by
default but treats `iat` only as a format check. An earlier version of this
note claimed both; the review corrected it. If GAU wants an `iat` window,
task 4.4 sets it through `set_jwt_verify_options`.

**PyLTI1p3 does not enforce nonce replay** (D-030). `validate_nonce` reaches
`CacheDataStorage.check_value`, which upstream only reads the key — so a
captured launch was replayable for the whole nonce lifetime. `check_value` has
exactly one call site in the library, `SessionService.check_nonce`, so
overriding it to delete is safe and confined to nonces. Verified against
`pylti1p3/session.py` at master.

`{"verify_aud": False}` in the library's PyJWT options looks like a hole and is
not one: `validate_registration` compares the `aud` claim against the
registration's client id itself. Worth knowing, because it means audience
checking would break silently if that comparison were ever removed.

LTI pages now carry a `frame-ancestors` policy of their own (D-031). Without it
`X_FRAME_OPTIONS = "DENY"` blanks every page in this module inside Canvas,
including the error page a student needs in order to report a failure.

**The independent review of 1.5 did not complete** — the agent stopped on an
account session limit before producing findings. Its highest-risk questions were
answered by hand instead: the `check_value` call-site audit above, decorator
ordering (`xframe_options_exempt` must wrap the view that returns the response,
so `canvas_framable` sits innermost), template autoescaping, and claim
extraction, which was hardened after the check — a `context` claim that is not
an object would have turned a verified launch into a 500. **A review of 1.5 is
still owed.**

**No tests, at the client's direction.** Task **1.16** owes all of: valid
launch, expired token, wrong `aud`, replayed nonce, unknown deployment,
missing state, and that each renders the error page rather than a traceback.

**Owed before 1.5 can be marked DONE:**

1. Rebuild the image, then `ruff check`, `ruff format --check`, `mypy .`,
   `pytest`.
2. A launch against a mock platform: valid launch renders the verified page;
   the same launch replayed is refused; a token with a past `exp` is refused.
3. Confirm the nonce key is gone from Redis database 3 after one launch.
4. Confirm the response carries `Content-Security-Policy: frame-ancestors …`
   and no `X-Frame-Options`.

**Points the next loops must respect:**

- The launch view currently ends at a verified-launch page. **Tasks 1.8, 1.9
  and 1.12** replace that page with provisioning, session establishment and
  role routing. The validation and error handling around it stay.
- **Task 4.4** must extend `frame-ancestors` to the whole application and
  should reuse `apps.lti.tool_conf.canvas_frame_ancestors`, not write a second
  policy.
- **No clock skew allowance is configured.** PyJWT enforces `exp` with zero
  leeway, so a server whose clock drifts from Canvas's rejects valid launches.
  Tasks **4.8** and **4.9** should confirm NTP on the VPS before blaming the
  tool for intermittent launch failures.
- **Task 1.10:** the state cookie is still the primary path;
  `enable_check_cookies()` remains unused.

**1.4 notes: implemented, host-verified and reviewed.**
`/lti/login/` generates `state` and `nonce`, stores both in the `lti_state`
cache — its own Redis logical database, per D-008 — with a **600 second**
lifetime, and redirects to the registered platform's authorisation URL.
`apps/lti/tool_conf.py` is the only place that knows PyLTI1p3's shape.

PyLTI1p3 is now a dependency. Every API used was **read from upstream source in
this loop**, not recalled: `DjangoCacheDataStorage(cache_name=…)`,
`DjangoSessionService`, `ToolConfAbstract`'s four abstract methods and its
`set_iss_has_many_clients` helper, `Registration`'s setters,
`Deployment.set_deployment_id`, `OIDCException`. None of it has been executed.

The library defaults the nonce lifetime to 86400 seconds. That is the width of
the replay window a nonce exists to close, and its own state cookie lasts five
minutes, so it is set to 600 (D-028).

**An independent review of 1.2–1.4 found thirteen issues; the substantive ones
are fixed and recorded in D-029.** Two mattered most:

- `apps/lti/tool_conf.py` was **untracked** while `views.py` imported it at
  module scope. Committing the index as it stood would have made the URLconf
  fail to import and every route return 500.
- The tool set only its private key, so PyLTI1p3 would have signed every JWT
  with no `kid` header — defeating the whole purpose of D-027 and failing at
  task 1.14 for no visible reason.

**No tests, at the client's direction.** Task **1.16** owes: login initiation
redirects to the registered auth URL, an unregistered issuer is refused, an
issuer with two registrations resolves by client id, state and nonce land in the
LTI cache and expire, a missing key file does not break a launch.

**Owed before 1.4 can be marked DONE:**

1. Rebuild the backend image — `pylti1p3` and `cryptography` are both new.
2. `mypy .` — the PyLTI1p3 override in `pyproject.toml` is unproven, and the
   `# type: ignore[misc]` on `PlatformToolConf` may turn out to be unnecessary.
3. `ruff check`, `ruff format --check`, `pytest`.
4. A real handshake against a mock platform: `/lti/login/` returns a 302 to the
   registered `auth_login_url` carrying `state`, `nonce`, `client_id`,
   `redirect_uri` and `login_hint`, and both `state` and `nonce` appear in
   Redis database 3 with a TTL at or below 600.

**Points the next loops must respect:**

- **Task 4.4** must extend `frame-ancestors` beyond the LTI views to the rest
  of the application, reusing `apps.lti.tool_conf.canvas_frame_ancestors`.
- **Task 1.10:** PyLTI1p3 already ships `enable_check_cookies()` for the
  blocked-third-party-cookie case. Use it rather than building a fallback.
- **Task 1.16** is now carrying the entire test debt for `apps.lti`. Nothing in
  this module is covered by CI, so review is currently its only gate.

**1.3 notes: implemented and host-verified.** `apps/lti/keys.py`
generates RSA 2048 keypairs and builds the JWKS; `create_lti_key` is the command;
`/lti/jwks/` is mounted and serves the public halves (D-026).

Keys are PKCS#8 PEM files in `LTI_TOOL_KEY_DIR`, mode `0600` in a `0700`
directory, written with `O_EXCL` so a `kid` collision can never overwrite a key.
Only the private half is stored — the public half is derived on demand, so the
two cannot drift apart.

`cryptography` is now a direct dependency. It is not an addition to the fixed
stack: PyLTI1p3 pulls it in through jwcrypto anyway, so the image gains nothing
new, but key generation should not depend on a library arriving by accident.

**No tests, at the client's direction.** Task **1.16** owes: JWKS shape and
public-members-only, empty key directory serving a valid document, unreadable
key skipped rather than fatal, generated key appearing in the JWKS, `O_EXCL`
refusing to overwrite.

**Owed before 1.3 can be marked DONE:**

1. Rebuild the backend image — `cryptography` is a new dependency and the
   current image does not contain it.
2. `manage.py create_lti_key`, then confirm the file is mode `0600` and the
   directory `0700`.
3. `GET /lti/jwks/` returns that `kid` with `n` and `e` and **no** `d`, `p` or
   `q`; verify the published modulus matches `openssl rsa -pubout` on the PEM.
4. `ruff check`, `ruff format --check`, `mypy .`, `pytest`.

**Points the next loops must respect:**

- **Task 4.8 must give `LTI_TOOL_KEY_DIR` a persistent volume.** Locally the
  `./backend:/app` bind mount covers it. On the server, without a volume,
  recreating the container destroys every key and every Canvas registration
  must be re-pointed at a new one.
- `/lti/jwks/` is the second deliberately unauthenticated route, after the
  health endpoints. Task **4.3**'s endpoint audit must list it as such, and
  task **4.4**'s rate limiting must cover it — Canvas fetches it unauthenticated
  and so can anyone else.
- Generating a key does **not** rotate anything. The `kid` goes into the file
  named by `LTI_PLATFORMS_FILE` and `sync_lti_platforms` applies it.

**Found while verifying 1.3, and fixed:** `core/urls.py` still pointed a reader
at `config/health.py`, a path the 0.8 rename removed. The 0.8 sweep searched for
`config.` and so never matched `config/`. DECISIONS.md entries written before
the rename keep their original wording — it is an append-only log, and D-024
records the move.

**0.8 notes: restructure done, not yet verified by the toolchain.** At the
client's direction (D-024): `backend/config/` is now `backend/core/`; every
migration lives in `backend/migrations/<app>/` wired through
`MIGRATION_MODULES`; `frontend/utils/` holds shared helpers. Moved with
`git mv`, so history follows the files.

References updated everywhere: settings, `manage.py`, WSGI/ASGI, Celery,
`docker-compose.yml`, `docker/backend.Dockerfile`, `.github/workflows/ci.yml`,
`.env.example`, `scripts/check_env_docs.py`, and ruff/mypy/pytest/django-stubs
configuration. A repository-wide search for the old package name returns
nothing.

`tests/test_structure.py` is new and guards the parts that fail silently: an app
missing from `MIGRATION_MODULES` gets no tables and raises nothing, and a stray
per-app `migrations/` directory would quietly take precedence.

**Owed when Docker testing resumes — run before anything else, in this order:**

1. Confirm `django_migrations` is absent or empty (D-009 still holds).
2. `manage.py makemigrations --check --dry-run` — no changes expected. If there
   are, regenerate `backend/migrations/accounts/0001_initial.py`.
3. `manage.py migrate`, then `ruff check`, `ruff format --check`, `mypy .`,
   `pytest` (36 existing, plus accounts and structure tests).
4. `docker compose -f docker-compose.yml up -d --wait` — the compose commands
   and the image now reference `core.wsgi` and `core.celery`, which has not been
   executed yet.

Not created, deliberately: `backend/utils/`, and constants, rate-limiting and
database modules under `core/`. Each is added when it holds real code — task 1.7
brings role constants, 4.4 brings rate limiting. An empty directory is a stub.

---

## Stage 2: Deliverable 2 — Interactive Textbook Reader

| Id | Task | Depends on | Status |
|---|---|---|---|
| 2.1 | `content.Book` model: uuid, title, slug, description, status, created/updated | 0.3 | **IN PROGRESS** |
| 2.2 | `content.ContentNode` model: uuid, book fk, parent fk, node_type (UNIT, CHAPTER, SECTION, SUBSECTION), title, position, materialised ancestry for efficient tree reads | 2.1 | **IN PROGRESS** |
| 2.3 | Tree service: full TOC in one query, resolve ancestors, flat reading order, next and previous across sibling and parent boundaries | 2.2 | **IN PROGRESS** |
| 2.4 | `versioning.ContentVersion` model: uuid, node fk, version_number, body (JSONB Tiptap), created_by, created_at, change_note, is_published, previous_version fk | 2.2 | **IN PROGRESS** |
| 2.5 | `courses.CourseBook` mapping model plus service resolving which book a launched course opens | 2.1, 1.6 | **IN PROGRESS** |
| 2.6 | Read API: `GET /api/books/:id/toc`, `GET /api/nodes/:id` returning published body plus prev/next, course-scoped and permission-checked | 2.3, 2.5, 1.11 | **IN PROGRESS** |
| 2.7 | Tiptap JSON renderer in React: headings, paragraphs, lists, tables with headers, figures with captions and alt text, blockquotes, callouts, references, links; every top-level node renders with `id={blockId}` | 0.4 | **IN PROGRESS** |
| 2.8 | Reader layout: collapsible TOC sidebar, breadcrumb, content pane, previous/next controls, mobile drawer TOC, sticky progress indicator | 2.6, 2.7 | TODO |
| 2.9 | `reader.ReadingPosition` model: user, book, node, block_id, scroll_ratio, updated_at, unique per user and book | 2.2 | TODO |
| 2.10 | Position save (debounced PATCH on section change and scroll) and restore (resume at node, scroll to block); "Continue reading" entry point | 2.9, 2.8 | TODO |
| 2.11 | Meilisearch index design: one document per content block with node path, chapter title, section title, plain text, block id, book id | 0.2 | TODO |
| 2.12 | Indexing Celery tasks: full reindex command, incremental reindex on publish, delete on unpublish | 2.11, 2.4 | TODO |
| 2.13 | Search API and UI: phrase search, highlighted snippets, results grouped by chapter, click navigates to the node and scrolls to the exact block | 2.12, 2.8 | TODO |
| 2.14 | Responsive pass: desktop, laptop, tablet, mobile; keyboard navigation for TOC and prev/next, focus management, sensible contrast | 2.8 | TODO |
| 2.15 | Tests: TOC integrity, prev/next at first and last node, published-only visibility, search returns correct block, position round-trip, cross-course node access denied | 2.13, 2.10 | TODO |

**2.1 notes: implemented and host-checked.** `content.Book` is
the root of the content tree, with `apps/content` wired into `LOCAL_APPS` and
`MIGRATION_MODULES`. Model and migration compared field by field: 7 of 7 match,
plus the ordering and the check constraint.

**Two gates decide visibility, not one** (D-053). A student sees content when
the book is published *and* the node's version is published (task 2.4). That
separation is what lets an editor rewrite chapter nine of a live textbook
without anyone seeing it.

DRAFT is the default, so a book created by the import pipeline cannot become
visible because someone forgot a step. ARCHIVED is not deleted — withdrawing a
book keeps its versions and the reading positions pointing into it.

The slug is a handle, never a reference: nothing stores one as a pointer,
because renaming it would otherwise move every reading position in the book.

10 tests added (118 in the suite now), still **unrun**.

**2.2 notes: implemented and host-checked.** `ContentNode` stores
the tree twice — a `parent` relation, which is the truth, and a materialised
`path` of zero-padded positions, which is that truth made sortable (D-054).
Model and migration compared: 9 of 9 fields, both check constraints, the index
and the ordering.

**The path logic was executed on this host**, from the shipped code:

```
Unit 1         0001
  Chapter 1    0001.0001
    Section 2  0001.0001.0002
    Section 10 0001.0001.0010
  Chapter 2    0001.0002
```

Five properties confirmed: text order is reading order (10 after 2 — the reason
for zero padding), a parent sorts before its own children, a subtree prefix
matches only descendants, the whole tree sorts into reading order, and **the
last section of chapter one precedes chapter two** — so prev/next across a
parent boundary needs no special case at all. That last one is what pays for
the design.

11 tests added (129 in the suite), still unrun.

**2.3 notes: implemented and host-checked.**
`apps/content/services.py` is the content module's public face:
`reading_order` (one query), `table_of_contents` (nested from it),
`ancestors_of` (one IN query on path prefixes) and `neighbours`.

**`neighbours` takes the reading order rather than querying** (D-055). The
caller already holds it for the contents sidebar, and it means the publication
filter is applied once: task 2.6 filters the order, and prev/next then cannot
navigate to a draft, because a node absent from the list has no neighbours
rather than the wrong ones.

Nesting is by depth, not parent id, so a filtered list nests without a second
pass and an irregular import still renders every node.

**Executed on this host** from the shipped code — a six-node book nests
correctly, prev/next crosses both a chapter and a unit boundary, the first and
last nodes have one side only, a node outside the order has neither, and a tree
with a skipped level still shows every node.

16 tests added (145 in the suite), including two that assert the query count.

**Owed before 2.3 can be marked DONE:** `migrate`, `mypy .`, `pytest` — the
query-count assertions in particular are the kind that only a real run settles.

**Points the next loops must respect:**

- **Task 2.6 must pass a published-only reading order into `neighbours`.** That
  is the single point where published-only navigation is enforced.

**Owed before 2.2 can be marked DONE:** `makemigrations --check`, `migrate`,
`mypy .`, `pytest`.

**Points the next loops must respect:**

- **Task 3.3's move and reorder must rewrite the paths of the whole moved
  subtree**, not just the node. A node whose path disagrees with its parent
  chain breaks every tree read, and nothing will complain.
- **Task 3.3 owns keeping sibling positions distinct.** The database does not:
  a partial unique constraint cannot be deferrable in PostgreSQL, so the
  ordering carries an `id` tiebreak instead.
- **Task 2.9's `ReadingPosition` must reference a node by uuid, never by path.**
  A reorder changes paths; it must not move anyone's place in the book.

**Owed before 2.1 can be marked DONE:** `makemigrations --check`, `migrate`,
`mypy .`, `pytest`.

**Points the next loops must respect:**

- **Task 2.5** must respect the status gate, not merely the presence of a
  course-to-book mapping.
- **Task 2.12** must remove a book's documents from the search index when it
  stops being published, or archived content stays findable.
- `slug` is unique across all books including archived ones, so re-using an
  archived book's slug fails. Better than two books answering one URL.

**2.4 notes: implemented and host-checked.** `apps/versioning`
holds `ContentVersion` — the inner of D-053's two gates — plus the module's
`services.py`. Model and migration compared mechanically rather than by eye:
**9 of 9 fields, 4 of 4 constraints and the ordering agree**.

**Four invariants are the database's, not the application's:**

| Constraint | What it prevents |
|---|---|
| one published version per node | "the published body" having two answers |
| `(node, version_number)` unique | two simultaneous publishes both becoming v3 |
| `version_number >= 1` | a numbering that starts nowhere |
| `previous_version` unique | history becoming a tree, so "what came before" is ambiguous |

**A published version is immutable, and the guard is cheap** (D-056). A row
loaded as published refuses to be saved again; the one exception is withdrawal,
which changes the flag and never the text. This deliberately does **not** work by
remembering the loaded body — that would deep-copy a whole chapter on every
reader page load, and a caller mutating `body` in place would slip past it
anyway. A boolean has neither weakness.

**Executed on this host**, lifted from the shipped source by AST because Django
is not installed here — **17 of 17 cases**. `validate_tiptap_document` accepts a
document, an empty document and an unknown node type inside it, and refuses a
string, a bare list, `None`, `{}`, a non-`doc` type, a missing `content` key and
a `content` that is not a list. The `save` guard allows a new row, a draft edit,
a publish and a withdrawal, and refuses only the re-save of an already-published
version.

`services.py` offers exactly four reads, each with a named consumer:
`published_version` and `published_versions_for` for task 2.6, `published_node_ids`
for the reading-order filter D-055 requires, and `history` for task 3.7. Nothing
speculative — allocating numbers, saving drafts and publishing are 3.6's.

31 test functions added, 36 cases with parametrisation (**176 in the suite**),
still **unrun**. Rule C.1 holds: `apps/versioning` imports no other module's
models, the foreign key names `content.ContentNode` lazily as a string, and
`services.py` takes `ContentNode` from `apps.content.services` (the D-044
precedent). No import cycle — `content` does not reach back.

**Owed before 2.4 can be marked DONE:**

1. `makemigrations --check --dry-run` — no changes expected. If there are,
   regenerate `migrations/versioning/0001_initial.py` rather than patching it.
   This is the first migration whose `initial = True` depends on another app's
   initial migration, so the dependency graph is exercised for the first time.
2. `migrate`, `ruff check`, `ruff format --check`, `mypy .`, `pytest`.
3. Confirm in PostgreSQL that `one_published_version_per_node` is a **partial**
   unique index, and that it is the index the planner uses for
   `published_versions_for` — the one-query claim rests on it.
4. Confirm `previous_version` uniqueness tolerates many NULLs, which is
   PostgreSQL's default and what every node's first version relies on.

**Points the next loops must respect:**

- **Task 3.6 must unpublish before it publishes, inside one transaction.** The
  partial unique index cannot be deferred (the same PostgreSQL limitation D-054
  hit with sibling positions), so publishing the next version while the current
  one is still published violates it halfway through.
- **Task 3.6 must call `full_clean()` before writing a body.** Django validators
  do not run on `save()` — exactly the trap D-025 hit with platform
  registrations. A test asserts this rather than assuming it.
- **Task 3.6 owns allocating `version_number`.** The model deliberately does not
  pick one: a model that quietly chose the next number would turn a race into
  two rows that both believe they are v3 instead of a loud failure.
- **Unsettled, and 3.6's to settle: how the working draft is identified.**
  `is_published = False` covers both "not yet published" and "superseded", so
  the natural reading is "the newest version of the node, when it is not the
  published one". That is not encoded anywhere and should not be guessed at
  twice.
- **Task 2.6 filters the reading order with `published_node_ids`** and passes the
  result to `content.services.neighbours`. That is the single point where
  published-only navigation is enforced (D-055).
- **Task 2.12 indexes from the published version and removes on withdrawal.**
  A version that stops being published must leave the search index, or a draft
  is reachable through search even though the reader will not navigate to it.
- **Task 3.7's "restore" is a forward step**, never a rewind: it creates a new
  draft whose `previous_version` is the current head. Which version it was
  restored *from* has no column and belongs in `change_note` until 3.7 decides
  it needs one.

**2.5 notes: implemented and host-checked.** `courses.CourseBook`
maps a course to the textbook it opens; `services/course_books.py` resolves that
mapping into an answer the reader can act on. Model and migration compared
mechanically: **6 of 6 fields, 2 of 2 constraints and the ordering agree**.

**The mapping is a row, not a column** (D-057). A course and a book have
different owners and different lifecycles, and the relationship is the thing an
administrator changes between terms — so changing it deactivates a row and
leaves a trace, rather than overwriting a field. Two constraints:
`(course, book)` unique, so moving a course back to a previous textbook reuses
that row; and one **active** mapping per course, so "which book does this course
open" cannot have two answers.

**The answer is a result, not a `Book | None`.** "This course has no textbook
yet" and "the textbook is not published yet" need different screens and have
different fixes — one is an administrator linking a book, the other publishing
one. Flattening both to None would move that decision to a guess at the call
site, which is the reasoning D-014 already applied on the frontend.

**An unpublished book is withheld, not merely flagged.** `CourseBookResolution.book`
is populated only when the book may be read, so a caller that ignores
`availability` gets nothing rather than a draft textbook.

**Executed on this host**, lifted from the shipped source by AST — **10 of 10
cases**. `book_for_course`, 4 of 4: no mapping, a published book, a draft book
and an archived book each resolve to the right availability, and the book is
carried only in the first. `_deep_link_title`, 6 of 6 (below).

**D-050's constant deep-link title is closed, which 2.5 owed.** Canvas's content
picker now shows the book's own title. `find_course` is new — a read-only lookup
on the D-032 identity, so that answering "which book does this course open"
cannot create a course as a side effect; a deep linking request is answered
before provisioning, and a question must not write a row.

`_deep_link_title` **never raises**, following `audit.claims_of` (D-051). Three
things go missing here legitimately — an account-level request carries no
course, a course nobody has launched has no row, and a course may have no
published book — and the generic title is a correct answer to all three. The
unexpected is logged and swallowed too, so a database hiccup cannot turn a
working deep linking request into an error page. Exercised on this host across
all six paths, the database failure included.

**Caught by that exercise, and fixed: a real defect I introduced.** Inserting
the helper into `views.py` placed it *between* `launch`'s decorators, so
`@csrf_exempt` and `@require_http_methods(["POST"])` moved onto the helper and
off the view. `/lti/launch/` would have rejected Canvas's cross-site POST on
CSRF — every launch in the product, broken. It is syntactically valid, so ruff
and the formatter both passed it; only running the code found it. The decorator
list of every view in the module is now asserted against `git HEAD` and matches.

`migrations/courses/0001_initial.py` was **amended** rather than followed by an
0002, and now depends on `content.0001_initial`. Safe only because nothing has
ever been applied (D-009) — this is the third task to rely on that, after 1.13
and 1.15.

26 test functions added, 27 cases with parametrisation (**202 in the suite**),
still **unrun**.

**Verified repo-wide while checking this task**, with scripts written for it:

- **All seven models now agree with their hand-written migrations** — Book,
  ContentNode, Course, CourseMembership, CourseBook, ContentVersion,
  LtiPlatform. This independently re-confirms the by-hand comparisons recorded
  for 1.2, 1.6, 2.1 and 2.2, which until now rested on reading.
- **198 of 198 first-party imported names resolve**, rule C.1 holds (no module
  imports another module's models), D-048 holds (no module core imports the
  shared package), and there are **no runtime import cycles** — TYPE_CHECKING
  imports excluded, since they are not runtime edges.

**Found and fixed while doing this:** `backend/services/__init__.py` still
claimed "no module imports this package", which D-048 corrected six tasks ago
and which `apps/lti/views.py` already contradicted. The docstring now states
the rule D-048 actually settled.

**Owed before 2.5 can be marked DONE:**

1. `makemigrations --check --dry-run` — no changes expected. The courses
   migration now depends on content's, so the **cross-app dependency graph is
   exercised for the first time**; a bad dependency shows up here as an
   unresolvable graph rather than a field mismatch.
2. `migrate`, `ruff check`, `ruff format --check`, `mypy .`, `pytest`.
3. Confirm `one_active_book_per_course` is a **partial** unique index in
   PostgreSQL, and that `link_course_to_book` survives being called twice
   concurrently for the same course.
4. Link the demonstration course to the nursing textbook end to end, which
   needs the course-to-book mapping GAU still owes.
5. A real deep linking request from Canvas shows the book's title in the
   content picker — **needs GAU's Canvas**, since the response is signed. The
   end-to-end test belongs with the mock platform D-052 defers to.

**Points the next loops must respect:**

- **There is no operator-facing way to create a mapping yet.** `link_course_to_book`
  is the safe path, but nothing exposes it — no command, no CMS screen. **Task
  3.2** owns the interface. Until then a mapping can only be made from a shell,
  which is enough for testing and not enough for GAU.
- **Task 2.6 applies both gates**: `book_for_course` for the book, then
  `versioning.services.published_node_ids` for the nodes (D-053). Neither
  implies the other — a published book may contain unpublished chapters, and a
  draft book may contain published ones.
- **Task 3.9's draft preview must be its own named path**, not a flag on
  `book_for_course`. A boolean that widens access is a boolean somebody
  eventually passes True by accident.
- **Task 1.14's deep-link picker** can now scope its choices to the course's
  book rather than offering the whole platform's content.

**2.6 notes: implemented and host-checked.** `apps/content/views.py`
serves the read API, mounted at `/api/` by `core/urls.py`. Three endpoints, all
course-scoped:

| Route | Answers |
|---|---|
| `GET /api/textbook/` | which book this launch opens, and if none, why not |
| `GET /api/books/<id>/toc/` | that book's contents, published parts only |
| `GET /api/nodes/<id>/` | one node's published body, breadcrumb, prev/next |

**Acceptance criterion 12 is demonstrable for the first time.** D-044 recorded
that `has_object_permission` had no caller, so nothing in the platform could
emit a cross-course refusal — criterion 12 "rests on 2.6, 1.16 and 4.3, and on
nothing before them". A reader launched into one course who asks for another
course's book, or a node from it, is now refused by name, and
`TestCrossCourseRefusal` asserts it seven ways.

**It is not `has_object_permission` that does it** (D-058), and that matters for
task 4.3. Content has no `course_id` for the permission to read, and a book
legitimately serves many courses, so resolving content → course is one-to-many
and cannot decide anything. The refusal runs the other way: the session names
the course, the course names one book (D-057), and a book id in the URL is only
ever *compared* against it. **`CourseScoped.has_object_permission` therefore
still has no caller** — 4.3 should either find it one or remove it as dead code.

**A third endpoint was added beyond the two in the backlog.** Nothing told the
reader which book to ask for, so `GET /api/books/:id/toc` was unreachable from
the frontend and task 2.8 would have been blocked. `/api/textbook/` also carries
D-057's three-way availability, which was otherwise unreachable from the UI and
so pointless.

**Both of D-053's gates, one place each.** The book gate is `book_for_course`;
the node gate filters the reading order once, before contents, breadcrumb and
prev/next are derived from it (D-055). Asserted directly: `next` steps over an
unpublished section rather than landing on it, and a breadcrumb under an
unpublished chapter shows a shorter trail rather than naming a chapter the
student cannot open.

**Executed on this host** — **10 of 10 cases**, the shaping logic lifted from
the shipped source by AST: breadcrumbs with a missing ancestor, a sibling that
must not be mistaken for one, an unrelated branch, a top-level node, and the
three response shapes.

26 test functions added, 30 cases with parametrisation (**228 in the suite**),
still **unrun**.

**A performance defect in 2.4, found by writing its consumer and fixed.**
`published_node_ids` was `set(published_versions_for(nodes))`, which loaded the
full Tiptap body of **every chapter in the book** in order to return a set of
ids — on every page load, for a table of contents that displays none of it. It
now reads one column with `values_list`. Nothing would have caught this: the
responses were identical and only the cost differed. 2.4 also named 2.6 as
`published_versions_for`'s consumer, which was wrong — 2.6 wants ids and one
body; the real consumer is task 2.12's indexing.

**The query-count tests assert an invariant, not a number.** A book with forty
chapters must cost exactly what a book with two costs. A magic constant would
have been a guess — nothing here has been run — and it would break on any
incidental change; the invariant is the thing actually worth protecting, and it
is what would have caught the defect above.

**Owed before 2.6 can be marked DONE:**

1. `migrate`, `ruff check`, `ruff format --check`, `mypy .`, `pytest`. The API
   tests are the first in this project to exercise the URLconf, DRF permissions
   and the session end to end, so they are the likeliest to need fixing on
   first run.
2. Confirm the two query-count invariants hold, and record the actual constants
   in this file once they are known.
3. Confirm DRF renders `PermissionDenied` as 403 and `NotFound` as 404 with
   `{"detail": …}`, which the frontend guards in 2.7/2.8 will be written
   against.
4. Walk a real launch through to a chapter, in Canvas — the first time the
   whole chain is exercised.

**Points the next loops must respect:**

- **Task 2.7's Tiptap renderer and 2.8's reader consume these shapes.** Their
  guards must validate recursively (D-015): `toc` nests arbitrarily deep, and
  `body` is a whole Tiptap document.
- **Task 2.8 must call `/api/textbook/` first** to learn the book id, and must
  render the two unavailable states as messages rather than as errors.
- **Task 2.10's reading position must not re-derive the published order.**
  `_published_order` is the single filter point; a second one will drift.
- **Task 3.9's preview needs its own endpoint**, not a flag on these. Every
  route here serves published content only, by construction.
- **Task 4.3** should note that these endpoints refuse by comparison rather
  than by object permission, and decide the fate of
  `CourseScoped.has_object_permission`.

**2.7 notes: implemented, and — unusually for this project — actually run.**
A renderer already existed from the interface preview (commit `1785d36`). It
covered headings, paragraphs, lists, tables with headers, figures, blockquotes,
callouts and links, and emitted `id={blockId}`. What it did not have is the
thing that makes it safe to point at real content: **a guard**.

`lib/content/parse.ts` is that guard — recursive, and the first real test of
D-015 on nested data. A node body is JSONB the backend never inspects beyond
its outer shape (D-056), so it reaches the reader as `unknown`. It is now
narrowed rather than cast.

**The guard has two biases, in opposite directions** (D-059):

| Level | Behaviour | Why |
|---|---|---|
| the document | strict — rejected outright | not a Tiptap document means nothing to show |
| a block | lenient — dropped, chapter renders | one malformed callout must not cost a whole section |
| inside a block | text preserved above all | losing a paragraph is always worse than losing its formatting |

So an unknown mark loses the emphasis and keeps the sentence, a heading at an
unsupported level is clamped to h2/h3 rather than discarded (the node's own
title owns the page's h1), a link with no destination keeps its text, and a
block that arrived with no `blockId` keeps its text and loses only its anchor.

**An unknown callout variant is never guessed at.** It renders as a neutral
`note`. Showing a callout kind this reader does not recognise as a "Practice
point" would understate something that might be a safety warning, and in a
nursing textbook that is not a cosmetic mistake.

`references` was the one block type in the backlog's list with no
implementation; it is added, rendered as an ordered list inside a labelled
`<section>`, and present in the preview sample so it is visible.

**The frontend now has a unit test runner, and it runs here.**
`playwright.unit.config.ts` points `@playwright/test` — already the pinned
runner (D-017) — at `tests/unit/`, with no browser and no stack. No dependency
was added and Section B's fixed stack is untouched. It is a separate config
because the e2e suite attaches to a running Compose stack by design and cannot
run without one; mixing them would have made the cheap tests as expensive as
the dear ones.

**38 unit tests, and they pass.** These are the first executed tests in the
project: `npx playwright test -c playwright.unit.config.ts` → **38 passed**.
`tsc --noEmit`, `eslint` and the **production build** (`NODE_ENV=production
npm run build`, 10 routes, exit 0) are all clean on this host. The unit suite is
wired into the CI frontend job as a step between TypeScript and the build.

So 2.7 is the first task in this project whose every gate has actually been
executed rather than reasoned about. The backend's have not.

**Two defects found by running things, which is the point:**

- `tsc` refused the new `note` variant until `CALLOUT_STYLE` covered it — the
  exhaustive `Record<CalloutVariant, …>` did its job in the second after the
  type changed. The backend has no equivalent loop.
- One test failed on first run. The expectation was wrong, not the code: when
  every mark on a run of text is dropped the `marks` key is omitted entirely
  rather than left empty, which is what `exactOptionalPropertyTypes` requires
  and what survives a round trip through JSON.

Also fixed while there: `key={blockId}` would have collided for two blocks
without a blockId, which is reachable now that such blocks are kept.

**Owed before 2.7 can be marked DONE:**

1. Render a real API response through the guard end to end, once 2.8 has the
   bindings. Everything so far is fixtures, and the shapes were written from
   `apps/content/views.py` rather than observed — so the one thing these tests
   cannot prove is that the two ends agree.
2. Confirm the new CI step runs on GitHub. The workflow has still never
   executed there (see 0.6), so this step is as unproven as the rest of it.
3. An accessibility pass over the rendered output — table scopes, the figure
   caption relationship and the callout `aria-label` are written as intended
   but have not been through a screen reader (task 2.14, then 4.6).

**Points the next loops must respect:**

- **Task 2.8 must put `parseContentDocument` in its binding** and never cast a
  body. It is a `Validator<T>` (D-014), so it drops straight into `request()`.
- **Task 2.8 must distinguish two failures**: a `malformed` error, which means
  the contract broke, and a document that parses to zero blocks, which means
  the content is empty. They need different screens.
- **Task 3.5's editor is the other half of this contract.** A node type it
  starts producing is invisible here until it is added to `types.ts` and
  `parse.ts` — silently, because an unknown block is dropped by design. Adding
  a node type is a change to both ends.
- **Task 2.10 must not assume every block has an anchor.** A block with no
  `blockId` renders without an `id`, so a reading position can point at a node
  that is present but not scrollable-to.
- **Task 2.13's search snippets** should reuse `utils/highlight.ts` and the
  same `blockId` anchors this renderer emits.

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
| 12 | Student, Faculty and Administrator access correctly restricted, cross-course denial included | 2.6, 4.3, 4.7 |
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
- **Is GAU's Canvas cloud-hosted or self-hosted, and will this platform ever
  serve a second institution?** Every Instructure-hosted Canvas shares one
  `iss`, so the course identity carries the `tool_platform` guid to keep two
  institutions apart (D-032). The answer decides whether that is merely
  correct or load-bearing — needed before **1.8**.
