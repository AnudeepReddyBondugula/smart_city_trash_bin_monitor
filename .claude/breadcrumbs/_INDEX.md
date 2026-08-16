# Breadcrumb index

This is the single source of truth for what's been documented as an
end-to-end flow in this repo. Each flow folder has `FLOW.md` (30-second
overview), `DETAILS.md` (function-level trace), and `DEBUG.md` (log
locations, grep patterns, commands, env vars, breakpoints). See
`.claude/skills/follow-breadcrumb/SKILL.md` for how to use this before
exploring the codebase directly, and `../README.md` for the repo overview.

## Flows

| Flow | Folder | Description |
|------|--------|-------------|
| Startup & telemetry generation | [`startup-and-telemetry/`](startup-and-telemetry/FLOW.md) | `main.py` entry → Kafka start → load `ACTIVE` bins → per-bin simulator loop publishing to Kafka |
| Graceful shutdown | [`graceful-shutdown/`](graceful-shutdown/FLOW.md) | SIGINT/SIGTERM → stop simulators → stop Kafka → dispose DB engine → exit |
| Configuration loading | [`config-loading/`](config-loading/FLOW.md) | Env vars → `get_settings()` → cached, validated `Settings` / `DATABASE_URL` |
| Database seeding | [`database-seeding/`](database-seeding/FLOW.md) | `seed.py` CLI → mock `SmartBin` rows in `smart_bins` |
| Table creation (schema init) | [`table-creation/`](table-creation/FLOW.md) | `create_tables.py` → `Base.metadata.create_all` |
| CI PR governance & pytest | [`ci-pr-governance/`](ci-pr-governance/FLOW.md) | PR → branch-type detection → feature-policy scope check + pytest run |

## Quick navigation (symptom → debug guide)

| Symptom | Debug guide |
|---------|-------------|
| No telemetry published / "Started 0 simulator(s)" | [`startup-and-telemetry/DEBUG.md`](startup-and-telemetry/DEBUG.md) |
| "Kafka not ready yet" / "Failed to send telemetry" | [`startup-and-telemetry/DEBUG.md`](startup-and-telemetry/DEBUG.md) |
| Process hangs or logs warnings on shutdown | [`graceful-shutdown/DEBUG.md`](graceful-shutdown/DEBUG.md) |
| pydantic `ValidationError` at startup / crash before `main()` | [`config-loading/DEBUG.md`](config-loading/DEBUG.md) |
| Env var change has no effect at runtime | [`config-loading/DEBUG.md`](config-loading/DEBUG.md) |
| `seed.py` crashes / prints an exception | [`database-seeding/DEBUG.md`](database-seeding/DEBUG.md) |
| `relation "smart_bins" does not exist` | [`table-creation/DEBUG.md`](table-creation/DEBUG.md) |
| PR rejected with "❌ Invalid change detected" | [`ci-pr-governance/DEBUG.md`](ci-pr-governance/DEBUG.md) |
| PR fails on unknown branch prefix | [`ci-pr-governance/DEBUG.md`](ci-pr-governance/DEBUG.md) |
| `pytest -v` fails in CI but not locally | [`ci-pr-governance/DEBUG.md`](ci-pr-governance/DEBUG.md) |

When adding or updating a flow, update both tables above in the same change.
