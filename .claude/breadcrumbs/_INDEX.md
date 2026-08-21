# Breadcrumb index

Each flow contains a short `FLOW.md`, detailed `DETAILS.md`, and troubleshooting
`DEBUG.md`. Verify cited source locations before relying on them because code
line numbers can move.

## Flows

| Flow | Folder | Description |
|---|---|---|
| Startup and telemetry | [`startup-and-telemetry/`](startup-and-telemetry/FLOW.md) | Start Kafka, load active bins, simulate state, and publish payloads. |
| Graceful shutdown | [`graceful-shutdown/`](graceful-shutdown/FLOW.md) | Signals, task cancellation, producer stop, and engine disposal. |
| Configuration | [`config-loading/`](config-loading/FLOW.md) | Environment variables through cached settings and connection URLs. |
| Schema migrations | [`schema-migrations/`](schema-migrations/FLOW.md) | Alembic revision discovery, upgrade, downgrade, and legacy adoption. |
| Database seeding | [`database-seeding/`](database-seeding/FLOW.md) | Generate Hyderabad-zone bins and commit them to `smart_bins`. |
| PR governance and tests | [`ci-pr-governance/`](ci-pr-governance/FLOW.md) | Detect branch type, enforce feature scope, and run pytest. |
| Fault injection | [`fault-injection/`](fault-injection/FLOW.md) | Make bins misbehave on purpose so every detector has something to detect. |
| Stream processing | [`stream-processing/`](stream-processing/FLOW.md) | Kafka to Spark: clean, deduplicate, dead-letter, aggregate, and write. |
| Alert detection | [`alert-detection/`](alert-detection/FLOW.md) | The per-bin stateful operator and its eleven alert types. |

## Symptom routing

| Symptom | Debug guide |
|---|---|
| No telemetry or zero simulators | [`startup-and-telemetry/DEBUG.md`](startup-and-telemetry/DEBUG.md) |
| Kafka unavailable or send failures | [`startup-and-telemetry/DEBUG.md`](startup-and-telemetry/DEBUG.md) |
| Shutdown warnings or hangs | [`graceful-shutdown/DEBUG.md`](graceful-shutdown/DEBUG.md) |
| Settings validation failure | [`config-loading/DEBUG.md`](config-loading/DEBUG.md) |
| Unknown Alembic revision or missing table | [`schema-migrations/DEBUG.md`](schema-migrations/DEBUG.md) |
| Seeding failure or unexpected zones | [`database-seeding/DEBUG.md`](database-seeding/DEBUG.md) |
| Branch policy or CI failure | [`ci-pr-governance/DEBUG.md`](ci-pr-governance/DEBUG.md) |
| No faults injected, or a detector never fires | [`fault-injection/DEBUG.md`](fault-injection/DEBUG.md) |
| Empty Spark output tables, or checkpoint problems | [`stream-processing/DEBUG.md`](stream-processing/DEBUG.md) |
| An alert fires too often, never, or wrongly | [`alert-detection/DEBUG.md`](alert-detection/DEBUG.md) |
| Bins missing from `bin_state_latest` | [`stream-processing/DEBUG.md`](stream-processing/DEBUG.md) |
