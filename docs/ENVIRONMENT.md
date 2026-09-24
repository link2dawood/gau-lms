# Environment configuration

Every setting the platform has comes from the environment. Nothing is
hard-coded — no Canvas URL, client id, deployment id, course id or role string
appears anywhere in the source. This document is the reference for all of it.

**Audience:** whoever builds, runs or deploys an environment.

- [Getting started](#getting-started)
- [How configuration is read](#how-configuration-is-read)
- [Reference](#reference)
- [Keeping this document honest](#keeping-this-document-honest)

---

## Getting started

```bash
cp .env.example .env
```

Then set the three values that have no usable default:

| Variable | Generate with |
|---|---|
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `POSTGRES_PASSWORD` | `openssl rand -base64 32` |
| `MEILI_MASTER_KEY` | `openssl rand -base64 32` |

`POSTGRES_PASSWORD` also appears inside `DATABASE_URL`; both must match.

Then:

```bash
docker compose up -d --wait      # local development, with fast refresh
```

The platform is at `http://localhost:8080` (or whatever `HTTP_PORT` is set to).

> **`docker compose up` is not what CI runs.** It loads
> `docker-compose.override.yml`, which swaps in the Next.js development server.
> To run the production build — what CI and the server use — bypass the
> override: `docker compose -f docker-compose.yml up -d --wait`.

`.env` is never committed. `.env.example` is, and carries a placeholder for
every variable.

### Port conflicts

`POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `MEILI_HOST_PORT` and `HTTP_PORT` are
host-side only and exist because collisions with other projects are routine.
Change them freely; nothing inside the compose network is affected, because
services reach each other by service name on the private bridge.

---

## How configuration is read

`backend/core/settings/env.py` is the only place the environment is read. It
is built on the standard library, and it is deliberately unforgiving:

- **A missing required variable raises at import, naming the variable.** The
  application refuses to start rather than starting misconfigured.
- **An unparseable boolean is an error, not `False`.** `DJANGO_DEBUG=Ture` fails
  loudly instead of silently shipping a production setting that looks
  configured.
- **An empty value means "not configured", not "off".** `get_bool`, `get_str`
  and `get_list` all fall back to their default for an empty variable.
- **A non-PostgreSQL `DATABASE_URL` is refused.** The content model depends on
  JSONB and hierarchical queries; a SQLite fallback would let tests pass against
  a database the platform never runs on.

Settings are split across `base.py` (shared), `dev.py`, `prod.py` and `test.py`.
The environment chooses between them with `DJANGO_SETTINGS_MODULE`.

### Production settings refuse to start when misconfigured

Under `core.settings.prod`, these are fatal rather than defaulted:

| Condition | Why it is fatal |
|---|---|
| `DJANGO_ALLOWED_HOSTS` empty | An unset host list must not mean "accept any `Host` header". |
| `DJANGO_CSRF_TRUSTED_ORIGINS` empty | Must name the exact `https://` origins served. |
| `MEILI_ENV` not `production` | `development` exposes the Meilisearch web UI and relaxes key checks. |

---

## Reference

Legend: **required** has no default and the application will not start without
it. *Development only* means production settings ignore or override it.

### Host ports

Local development only. The deployed server exposes 80 and 443 (task 4.8).

| Variable | Default | Purpose |
|---|---|---|
| `HTTP_PORT` | `8080` | Where Nginx — the single entry point — is published on the host. |
| `POSTGRES_HOST_PORT` | `5432` | For `psql` from the host. Bound to `127.0.0.1` only. |
| `REDIS_HOST_PORT` | `6379` | For `redis-cli` from the host. Bound to `127.0.0.1` only. |
| `MEILI_HOST_PORT` | `7700` | For the Meilisearch UI in development. Bound to `127.0.0.1` only. |

### PostgreSQL

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_DB` | `gau_textbook` | Database name, used by the postgres container on first start. |
| `POSTGRES_USER` | `gau` | Role name, used by the postgres container on first start. |
| `POSTGRES_PASSWORD` | **required** | Role password. Also embedded in `DATABASE_URL`; the two must agree. |
| `DATABASE_URL` | **required** | What Django connects with. Must be `postgres://`. Host and port are the *service name* (`postgres:5432`), not `localhost`. |
| `DATABASE_CONN_MAX_AGE` | `60` | Seconds a connection is reused between requests. The reader issues many small queries; reconnecting each time is pure overhead. |

> Changing `POSTGRES_DB`, `POSTGRES_USER` or `POSTGRES_PASSWORD` after the first
> start has no effect: those are read only when the data directory is
> initialised. To change them, remove the `pg_data` volume — which destroys the
> data — or alter the role in SQL.

### Redis

Four logical databases, separated by purpose, so clearing the cache cannot drop
a queued import or an in-flight LTI nonce.

| Variable | Default | Purpose |
|---|---|---|
| `REDIS_CACHE_URL` | **required** | Cache and sessions. Database 0. Safe to flush. |
| `CELERY_BROKER_URL` | **required** | Queued jobs. Database 1. Flushing loses queued imports. |
| `CELERY_RESULT_BACKEND` | **required** | Task results. Database 2. |
| `LTI_STATE_REDIS_URL` | **required** | OIDC state and nonces during a launch. Database 3. Flushing breaks launches in progress. |
| `SESSION_REDIS_URL` | *(required)* | Redis database holding sessions. Separate from the page cache because a session is not cache: clearing a stale page must not sign every reader out, and LRU eviction must not be able to drop one. See DECISIONS.md D-039. |

### Meilisearch

| Variable | Default | Purpose |
|---|---|---|
| `MEILISEARCH_URL` | **required** | Reached by service name inside the network. |
| `MEILI_MASTER_KEY` | **required** | Minimum 16 bytes. Without it Meilisearch accepts unauthenticated requests. |
| `MEILI_ENV` | `development` | Must be `production` on any deployed environment; production settings refuse to start otherwise. |
| `MEILISEARCH_INDEX_PREFIX` | `gau` | Namespaces index names so staging and production can share an instance without one reindex clobbering the other. |

### Django core

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | **required** | Signs sessions and CSRF tokens. Rotating it invalidates every active session. Never reuse across environments. |
| `DJANGO_SETTINGS_MODULE` | `core.settings.dev` | One of `core.settings.{dev,prod,test}`. |
| `DJANGO_DEBUG` | `true` | *Development only.* Production forces it off. |
| `DJANGO_ALLOWED_HOSTS` | dev: `localhost,127.0.0.1,backend,nginx,testserver` | Comma-separated hostnames. **Required and non-empty in production**, where there is no default. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | dev: `http://localhost:8080,http://127.0.0.1:8080` | Comma-separated absolute origins. **Required and non-empty in production**, where there is no default, and `https://` there. |
| `PLATFORM_BASE_URL` | **required** | Public origin of the tool, no trailing slash. Builds the LTI redirect URIs and the JWKS URL given to the Canvas administrator. |
| `CANVAS_FRAME_ANCESTORS` | *(empty)* | Canvas hosts permitted to embed the reader in an iframe. Enforced as a CSP `frame-ancestors` directive in task 4.4. |
| `LTI_PLATFORMS_FILE` | *(unset)* | Path to the JSON file listing the Canvas platforms the tool trusts (issuer, client id, deployment ids, the three Canvas endpoint URLs). Applied with `manage.py sync_lti_platforms`. Unset means no platform can launch the tool. Gitignored — it names a specific institution's Canvas. See DECISIONS.md D-025. |
| `LTI_TOOL_KEY_DIR` | `backend/lti-keys` | Directory holding this tool's RSA private keys, one PKCS#8 PEM per key named by its `kid`, mode `0600`. Created by `manage.py create_lti_key`; the public halves are served at `/lti/jwks/`. Gitignored. **Must be a persistent volume on the server (task 4.8)** — losing it means re-pointing every Canvas registration at a new key. See DECISIONS.md D-026. |
| `DJANGO_LOG_LEVEL` | `INFO` | Root log level. |
| `DJANGO_LOG_SQL` | `false` | *Development only.* Echoes every SQL statement; very noisy. |
| `DJANGO_LANGUAGE_CODE` | `en-us` | |
| `DJANGO_TIME_ZONE` | `UTC` | Stored data is timezone-aware; this is the display default. |

### Production security

Applied only under `core.settings.prod`. The defaults are correct; change them
only with a specific reason.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECURE_SSL_REDIRECT` | `true` | HTTPS is mandatory for LTI 1.3. |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` | One year. |
| `DJANGO_HSTS_INCLUDE_SUBDOMAINS` | `true` | |
| `DJANGO_HSTS_PRELOAD` | `false` | Enable only once the domain is permanently HTTPS-only. Preload submission is difficult to reverse. |

Production also sets, without a variable: `SESSION_COOKIE_SECURE`,
`CSRF_COOKIE_SECURE`, and `SameSite=None` on both. The reader runs inside a
Canvas iframe, so its cookies are cross-site by definition, and browsers honour
`SameSite=None` only together with `Secure`.

### Limits and tuning

| Variable | Default | Purpose |
|---|---|---|
| `SESSION_COOKIE_AGE` | `43200` | 12 hours. A Canvas launch is a working session, not a long-lived login. |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | `10485760` | 10 MB cap on the **non-file** part of a request — JSON and form fields. It does not apply to uploaded files. The largest legitimate body is one section's Tiptap JSON. |
| `FILE_UPLOAD_MAX_MEMORY_SIZE` | `10485760` | Point at which an uploaded file is streamed to disk rather than held in memory. **Not a size limit.** |
| `GUNICORN_WORKERS` | `2` | |
| `GUNICORN_TIMEOUT` | `60` | Seconds before a worker is killed. |
| `CELERY_CONCURRENCY` | `2` | Worker processes. |
| `CELERY_TASK_TIME_LIMIT` | `1800` | 30 minutes. A 338-page PDF import is the long pole. |
| `CELERY_TASK_SOFT_TIME_LIMIT` | `1500` | Raises an exception the task can catch and report. |

> **The ceiling on an uploaded file is not a Django setting.** It is
> `client_max_body_size` in `docker/nginx/nginx.conf`, currently 64 MB. The two
> Django upload settings above are routinely mistaken for it; neither limits the
> size of a document import.

### Frontend

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | *(empty)* | What the **browser** uses. Empty means same-origin, which is correct whenever Nginx fronts both — the normal case. |
| `INTERNAL_API_BASE_URL` | `http://backend:8000` | What the **server** uses during React Server Component rendering, reaching Django over the private network. |

> Only `NEXT_PUBLIC_`-prefixed variables exist in the browser bundle. Never put a
> secret behind that prefix — it ships to every reader.

---

## Keeping this document honest

Configuration documentation rots silently: a setting is added in code and nobody
updates the template, so the next person to build an environment discovers it as
a crash.

```bash
python3 scripts/check_env_docs.py
```

This compares what the settings read, what Compose interpolates and what the
frontend reads against what `.env.example` declares, and fails if they disagree.
Run it whenever a setting is added or removed, and update this reference in the
same change.
