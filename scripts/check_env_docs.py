#!/usr/bin/env python3
"""Keep .env.example honest.

Documentation about configuration rots silently: a setting is added in code and
nobody adds it to the template, so the next person to build an environment
discovers it as a crash. Or a setting is removed and the template keeps
advertising it, so someone configures something that does nothing.

This compares three sources and fails if they disagree:

  * variables the Django settings read, through core/settings/env.py
  * variables docker-compose.yml and its override interpolate
  * variables the frontend reads from process.env

against what .env.example declares.

It also checks that the CI backend job supplies every variable the settings
*require*. That job maintains its environment by hand rather than copying
.env.example, so it drifts silently — and because mypy's Django plugin imports
the settings module, a missing required variable surfaces there as a plugin
failure rather than as the configuration error it is.

Run from the repository root:

    python3 scripts/check_env_docs.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Supplied by the container runtime, the compose file itself, or a test — not
# by the operator, so they do not belong in .env.example.
NOT_OPERATOR_SUPPLIED = frozenset(
    {
        "POSTGRES_INITDB_ARGS",
        "MEILI_DB_PATH",
        "MEILI_NO_ANALYTICS",
        "NODE_ENV",
        "PORT",
        "HOSTNAME",
        "CI",
        "PLAYWRIGHT_BASE_URL",
        "NEXT_TELEMETRY_DISABLED",
        "PROBE",  # fixture name used by tests/test_env.py
    }
)

READER_CALL = re.compile(
    r'(?:require_str|get_str|get_bool|get_int|get_list)\(\s*"([A-Z0-9_]+)"'
)
OS_ENVIRON = re.compile(r'os\.environ(?:\.get|\.setdefault|\.pop)?\(\s*"([A-Z0-9_]+)"')
COMPOSE_INTERPOLATION = re.compile(r"\$\{([A-Z0-9_]+)")
COMPOSE_LITERAL_ENV = re.compile(r"^\s{6}([A-Z][A-Z0-9_]+):\s", re.M)
PROCESS_ENV = re.compile(r"process\.env\.([A-Z0-9_]+)")
DECLARATION = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.M)
REQUIRED_CALL = re.compile(r'require_str\(\s*"([A-Z0-9_]+)"')
CI_JOB_ENV = re.compile(r"^      ([A-Z][A-Z0-9_]+):", re.M)


def backend_variables() -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "backend").rglob("*.py"):
        # Tests set throwaway names; they are not configuration.
        if "tests" in path.parts:
            continue
        text = path.read_text()
        found.update(READER_CALL.findall(text))
        found.update(OS_ENVIRON.findall(text))
    return found


def compose_variables() -> set[str]:
    found: set[str] = set()
    for name in ("docker-compose.yml", "docker-compose.override.yml"):
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text()
        found.update(COMPOSE_INTERPOLATION.findall(text))
        found.update(COMPOSE_LITERAL_ENV.findall(text))
    return found


def frontend_variables() -> set[str]:
    found: set[str] = set()
    for pattern in ("*.ts", "*.tsx", "*.mjs"):
        for path in (ROOT / "frontend").rglob(pattern):
            if "node_modules" in path.parts or ".next" in path.parts:
                continue
            found.update(PROCESS_ENV.findall(path.read_text()))
    return found


def declared_variables() -> set[str]:
    return set(DECLARATION.findall((ROOT / ".env.example").read_text()))


def required_variables() -> set[str]:
    """Variables the settings refuse to start without."""
    found: set[str] = set()
    for path in (ROOT / "backend" / "core" / "settings").glob("*.py"):
        found.update(REQUIRED_CALL.findall(path.read_text()))
    return found


def ci_backend_variables() -> set[str]:
    """What the CI backend job puts in the environment.

    That job hand-maintains its env block instead of copying .env.example, so
    it is the one place that can fall behind without anything saying so.
    """
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    if not workflow.exists():
        return set()
    text = workflow.read_text()
    start = text.find("name: Backend")
    end = text.find("name: Frontend", start)
    if start == -1:
        return set()
    return set(CI_JOB_ENV.findall(text[start : end if end != -1 else len(text)]))


def main() -> int:
    used = (backend_variables() | compose_variables() | frontend_variables()) - NOT_OPERATOR_SUPPLIED
    declared = declared_variables()

    missing = sorted(used - declared)
    unused = sorted(declared - used)

    print(f"read by code or compose : {len(used)}")
    print(f"declared in .env.example: {len(declared)}")

    if missing:
        print("\nUsed but not declared — an operator cannot know to set these:")
        for name in missing:
            print(f"  {name}")
    if unused:
        print("\nDeclared but never read — dead configuration, or a typo in one of the two:")
        for name in unused:
            print(f"  {name}")

    absent_from_ci = sorted(required_variables() - ci_backend_variables())
    if absent_from_ci:
        print("\nRequired by the settings but absent from the CI backend job:")
        for name in absent_from_ci:
            print(f"  {name}")
        print(
            "  mypy imports the settings module, so this fails there as a plugin\n"
            "  error rather than as the missing configuration it is."
        )

    if missing or unused:
        print("\n.env.example is out of step with the code. Update it, and docs/ENVIRONMENT.md.")
        return 1
    if absent_from_ci:
        return 1

    print("\n.env.example matches the code, and CI supplies every required variable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
