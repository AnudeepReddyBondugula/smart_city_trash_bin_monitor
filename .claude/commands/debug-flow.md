---
description: Walk the exact call chain of a named flow, printing file:line at each hop.
argument-hint: <flow-name>
---

# /debug-flow <flow-name>

Traces a named execution flow through this codebase hop-by-hop, citing
`file:line` at each step, using the verified breadcrumbs in
`.claude/breadcrumbs/`.

## How to use

`$ARGUMENTS` is the flow name. Match it (case-insensitive, fuzzy) to one of the
breadcrumb folders:

| Flow name / aliases                                  | Breadcrumb folder |
| ---------------------------------------------------- | --------------- |
| `startup`, `telemetry`, `simulation`, `main`         | `.claude/breadcrumbs/startup-and-telemetry/` |
| `shutdown`, `graceful-shutdown`, `signal`            | `.claude/breadcrumbs/graceful-shutdown/` |
| `config`, `settings`, `env`                          | `.claude/breadcrumbs/config-loading/` |
| `seed`, `seeding`, `mock-data`                       | `.claude/breadcrumbs/database-seeding/` |
| `alembic`, `schema`, `migration`                     | `.claude/breadcrumbs/schema-migrations/` |
| `ci`, `pr`, `governance`, `pipeline`, `pytest`       | `.claude/breadcrumbs/ci-pr-governance/` |

Each folder has `FLOW.md` (high-level trace), `DETAILS.md` (function-level
trace), and `DEBUG.md` (log locations, grep patterns, commands, breakpoints).
`.claude/breadcrumbs/_INDEX.md` lists all flows plus a symptom → `DEBUG.md`
quick-navigation table.

## Steps

1. Resolve `$ARGUMENTS` to a breadcrumb folder above. If nothing matches, check
   `.claude/breadcrumbs/_INDEX.md`'s Flows table; if still nothing matches, list
   the available flows and ask which one.
2. Read `FLOW.md`, then `DETAILS.md` for that folder (skip `DEBUG.md` unless
   the request is about debugging).
3. **Verify before presenting** — open each cited `file:line` and confirm it
   still says what the breadcrumb claims (line numbers drift as code changes).
4. Present the trace as an ordered list: entry point → each hop → exit, with the
   (re-verified) `file:line` and a one-line description per hop, plus the "where
   errors surface" / `DEBUG.md` notes.
5. If any citation has drifted, correct it inline and note that the breadcrumb
   file should be updated (or suggest `/breadcrumb-creator`).

## Related

- Breadcrumb-first exploration: `.claude/skills/follow-breadcrumb/SKILL.md`.
- Subsystem context: `.claude/skills/*/SKILL.md` (index: `.claude/skills/index.md`).
- Root index: `.claude/README.md`.
