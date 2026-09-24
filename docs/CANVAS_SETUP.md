# Connecting the Interactive Textbook to Canvas

Written for the Canvas administrator at GAU, with the steps the platform
operator performs marked **[operator]**. Neither side can finish alone: Canvas
issues identifiers the platform needs, and the platform publishes a key Canvas
needs.

Allow about thirty minutes, and expect to exchange two short messages.

---

## Before you start

| You need | Why |
|---|---|
| Canvas admin rights on the account the textbook will serve | Only an account admin can create a developer key |
| The platform's address, e.g. `https://textbook.gau.edu.tr` | Every URL below is built from it |
| A test course with a student and a teacher in it | So the connection can be proved before anyone relies on it |

The platform must be reachable over **HTTPS**. Canvas will not accept a
developer key otherwise, and the session cookie the textbook depends on cannot
be set over plain HTTP.

---

## Step 1 — [operator] Generate the tool's signing key

```
docker compose run --rm backend python manage.py create_lti_key
```

This prints a key id. The key itself stays on the server and is never sent to
Canvas; Canvas reads the public half from the URL in step 2.

## Step 2 — [operator] Produce the configuration JSON

```
docker compose run --rm backend python manage.py lti_tool_config
```

Every URL in the output is derived from the platform's configured address, so
the JSON is always correct for the environment it was generated on. Do not
copy it from an email or from this document — generate it.

Add `--privacy-level` if GAU has decided on something other than the default;
see **What Canvas will share** below.

Send the output to the Canvas administrator.

## Step 3 — Create the developer key in Canvas

1. **Admin → Developer Keys → + Developer Key → + LTI Key**
2. Set **Method** to **Paste JSON**
3. Paste the JSON from step 2
4. **Save**, then switch the key's state from **Off** to **On**

Copy the **Client ID** — the long number shown in the key's Details column. It
looks like `10000000000123`.

## Step 4 — Install the app

Install it where the textbook should appear. Account level makes it available
to every course in that account; course level is the safer place to start.

1. **Settings → Apps → View App Configurations → + App**
2. Set **Configuration Type** to **By Client ID**
3. Paste the Client ID from step 3, and **Submit**

Then open **Settings → Apps → View App Configurations**, find the app, and from
its gear menu choose **Deployment Id**. Copy it. It looks like `12:a1b2c3…`.

## Step 5 — Send three values back to the operator

| Value | Where it came from |
|---|---|
| **Issuer** | `https://canvas.instructure.com` for Canvas Cloud; your Canvas URL if self-hosted |
| **Client ID** | Step 3 |
| **Deployment ID** | Step 4 |

## Step 6 — [operator] Register the platform

Put them in the file named by `LTI_PLATFORMS_FILE`, together with the key id
from step 1 and the three Canvas endpoints:

```json
[
  {
    "issuer": "https://canvas.instructure.com",
    "client_id": "10000000000123",
    "deployment_ids": ["12:a1b2c3..."],
    "auth_login_url": "https://<canvas-host>/api/lti/authorize_redirect",
    "auth_token_url": "https://<canvas-host>/login/oauth2/token",
    "jwks_url": "https://<canvas-host>/api/lti/security/jwks",
    "tool_key_id": "<the key id from step 1>",
    "is_active": true
  }
]
```

Then apply it:

```
docker compose run --rm backend python manage.py sync_lti_platforms --dry-run
docker compose run --rm backend python manage.py sync_lti_platforms
```

The file is never committed — it names a specific institution's Canvas.

## Step 7 — Prove it

In the test course, open the textbook from the course navigation. Then, as a
**student** in that course, do the same. Both must reach the textbook without
being asked to sign in again, and neither should be asked to create an account.

---

## What Canvas will share

The `privacy_level` in the configuration decides what Canvas tells the
textbook about each person. **This is GAU's decision, not a technical one.**

| Level | Canvas sends | Consequence |
|---|---|---|
| `public` *(default)* | Name and email | The reader is greeted by name; support can identify a user from a report |
| `name_only` | Name | No email held by the platform |
| `email_only` | Email | No name shown in the interface |
| `anonymous` | Neither | The textbook still works; nobody can be identified in it |

The textbook works at every level. It never stores more than Canvas sends, and
it keeps no password — Canvas remains the only way in.

---

## When a launch fails

Every launch is recorded, accepted or refused, with a reason. Ask the operator
for the launch log before changing anything in Canvas: it distinguishes
failures that look identical from the student's side.

| What the student sees | Likely cause | Where to fix it |
|---|---|---|
| "This textbook is not set up for your Canvas" | The issuer and client id are not registered, or the key is off | Step 6, or turn the key On in step 3 |
| "This textbook is not installed here" | Registered, but this deployment id is not listed | Add the deployment id from step 4 and re-run step 6 |
| "This launch could not be verified" | An expired or reused link; or the server clock has drifted from Canvas | Reopen from Canvas; if it persists, check time synchronisation on the server |
| "Canvas did not send enough information" | The launch carried no course context | Check the placement; account-level placements have no course |
| A blank frame, or a prompt to open a new tab | The browser is blocking cookies for framed content | Expected — use the "Open in a new tab" button; Safari does this by default |

## Keeping it working

- **Rotating the key.** Generate a new one (step 1), set `tool_key_id` to it
  and re-run step 6. Do not delete the old key file until every Canvas
  registration has moved, because it is still published for anything signed
  with it.
- **Changing the platform's address.** The URLs in the developer key must be
  updated to match. Regenerate the JSON (step 2) and edit the key in Canvas.
- **Removing someone from a course.** Canvas does not notify the textbook.
  The roster is reconciled on a schedule — ask the operator what
  `ROSTER_SYNC_INTERVAL_SECONDS` is set to; it is how long access persists
  after an unenrolment.
