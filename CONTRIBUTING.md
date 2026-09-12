# Contributing — GAU Interactive Textbook Platform

This document defines the branch strategy, commit conventions and pull-request
workflow for Phase 1. It is the rulebook for task **0.1**; every later task
follows it.

## 1. Branch strategy

Trunk-based development with short-lived task branches.

| Branch | Role |
|---|---|
| `main` | Always deployable. Protected. Every commit on `main` has passed CI. Deploys to **staging** automatically once the pipeline exists (task 0.6). |
| `feat/<task-id>-<slug>` | One backlog task from `PROGRESS.md`. Merged by PR, then deleted. |
| `fix/<slug>` | Bug fix outside the backlog (acceptance-testing fallout, Sprint 4). |
| `chore/<slug>` | Dependency bumps, tooling, documentation-only changes. |

Rules:

- **One branch per backlog task.** The branch name carries the task id, so the
  branch, the PR, the commit trail and `PROGRESS.md` all agree on what was built.
  Example: `feat/1.5-lti-launch-endpoint`.
- **Branch from current `main`.** Rebase onto `main` before requesting review; do
  not merge `main` into a task branch.
- **Never commit directly to `main`.** Including the first loop.
- **Squash merge into `main`.** One task becomes one commit, whose subject is the
  task id and title. History stays readable as the Phase 1 build log.
- **Delete the branch after merge.** Task branches are disposable.
- Production releases are cut by tagging a commit on `main` as `v0.<sprint>.<n>`
  (deployment detail lands in task 4.8).

## 2. Commit messages

```
<type>(<scope>): <summary>

<body: what and why, not how>

Task: <backlog id>
```

- `type`: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`.
- `scope`: the Django app or frontend area — `lti`, `accounts`, `courses`,
  `content`, `versioning`, `reader`, `cms`, `imports`, `search`, `frontend`,
  `infra`, `docs`.
- Subject in the imperative mood, no trailing full stop, under 72 characters.

## 3. Pull requests

Every change reaches `main` through a PR using
`.github/pull_request_template.md`. A PR is mergeable only when:

1. CI is green — ruff, mypy, pytest, eslint, tsc, `next build` (task 0.6).
2. The **Evidence** section contains pasted real output from a passing test or a
   verified command. An assertion that something works is not evidence.
3. Every box in the **Architecture checklist** is ticked or explicitly justified
   in the PR body. The checklist mirrors the non-negotiable architecture rules:
   module boundaries, UUID identity, non-destructive versioning, learning-record
   separation, Canvas as the authority for identity and enrollment, no
   hard-coding, structured content, default-deny authorisation, published-only
   student visibility, async for slow work.
4. No `TODO` markers, stub returns, commented-out code or placeholder data
   remain in the diff.
5. `PROGRESS.md` is updated in the same PR, and `DECISIONS.md` is appended to if
   the change made a decision that future work must respect.

## 4. Definition of done

A task is `DONE` only when its code is merged, its tests pass, and the passing
output is recorded. If a task cannot be completed because something outside the
repository is missing — a Canvas sandbox, a developer key, a branding asset, a
client decision — it is marked `BLOCKED` in `PROGRESS.md` with the specific
question, and the next task begins. Guessing is not an option; asking is.

## 5. Dependencies

The technology stack is fixed. Adding any runtime dependency outside it requires
an entry in `DECISIONS.md` and explicit approval before the code is written.
Development-only tooling that does not ship (formatters, test helpers) may be
added freely and noted in the PR.
