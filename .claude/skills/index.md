# Skill registry

This directory holds the reusable agent workflows for this repository. Each
skill has a `SKILL.md` with the full instructions. Use this page to choose
the right entry point before loading the detailed skill.

## Debugging and navigation

| Skill | Use it for | What it produces or does |
|---|---|---|
| [follow-breadcrumb](follow-breadcrumb/SKILL.md) | Finding where a flow is implemented or debugging a documented workflow | Reads `.claude/breadcrumbs/_INDEX.md` and matching flow docs first, then reports the relevant path, files, and verification points |
| [breadcrumb-creator](breadcrumb-creator/SKILL.md) | Documenting a workflow that isn't covered yet | Creates or updates a `.claude/breadcrumbs/` flow with FLOW, DETAILS, DEBUG, and index entries |

## Development

| Skill | Use it for | What it produces or does |
|---|---|---|
| [simulation-engine](simulation-engine/SKILL.md) | Working on `Bin`, `BinSimulator`, `SimulationManager`, the tick loop, or telemetry generation | Subsystem context for the simulation core |
| [database](database/SKILL.md) | Working on the SQLAlchemy async engine, `SmartBin`/`smart_bins`, schema creation, or seeding | Subsystem context for persistence |
| [kafka](kafka/SKILL.md) | Working on the `KafkaClient` producer, message format/keys, retries, topics, or broker config | Subsystem context for telemetry publishing |
| [spark](spark/SKILL.md) | Working on the stream-processor: Structured Streaming, cleaning and dead letters, windowed aggregates, the stateful operator, checkpoints, or the batch rollups | Subsystem context for stream processing |
| [config](config/SKILL.md) | Working on `Settings`/`get_settings()`, env vars, `DATABASE_URL`, or `.env` files | Subsystem context for configuration |
| [testing](testing/SKILL.md) | Writing/running/debugging pytest tests, fixtures, mocks, or docstring hooks | Subsystem context for the test suite |
| [ci-cd](ci-cd/SKILL.md) | Working on GitHub Actions, branch naming, or PR governance/scope rules | Subsystem context for CI/CD |
| [writeup](writeup/SKILL.md) | Turning user-provided content into a presentable page | Creates one self-contained HTML page containing only the requested content |

## Choosing quickly

- Need to understand an existing flow? Start with `follow-breadcrumb`.
- Need to create or repair its documentation? Use `breadcrumb-creator`.
- Need to implement/debug a specific subsystem? Load the matching skill above.

When adding or renaming a skill, update this registry in the same change.
Keep the table sentence-level and move procedural detail into the skill's
`SKILL.md`.
