# ADR 001: Use AsyncIO for concurrent bin simulation

- **Status:** Accepted (reflects current implementation)
- **Source note:** *Inferred from the codebase, not an original design record.*
  No written ADR predates this file; the reasoning below is reconstructed from
  code structure, docstrings, and dependencies. Points tied to specific code are
  cited; the rest is inferred.

---

## Context

The service must simulate a large fleet of smart bins **concurrently**, each
emitting telemetry on a fixed interval (`SIMULATION_INTERVAL`, default 5s). The
per-bin workload is almost entirely I/O-bound waiting: sleep between ticks, then
`await` a network publish to Kafka; the actual computation (`_simulate`,
`to_payload`) is trivial. The dependencies are async-native — `aiokafka` and
SQLAlchemy's async engine with `asyncpg` (`requirements.txt`).

Options for concurrency:

1. **Threads** — one thread per bin.
2. **Processes** — one process per bin (or a pool).
3. **AsyncIO** — one event loop, one task per bin.

## Decision

Use a single-process **asyncio** model: one event loop, one `asyncio.Task` per
bin.

Evidence in code:

- `main()` is `async` and launched with `asyncio.run(main())`
  (`src/main.py:17, 72`).
- Each `BinSimulator.start()` schedules its loop as a task —
  `self._task = asyncio.create_task(self._run())` (`bin_simulator.py:74`) — and
  `_run()` `await`s Kafka then `asyncio.sleep(SIMULATION_INTERVAL)`
  (`bin_simulator.py:131-142`).
- I/O libraries are async: `AIOKafkaProducer` (`kafka_producer.py`) and
  `create_async_engine(... postgresql+asyncpg ...)` (`database.py`,
  `config.py`).
- Shutdown is coordinated with an `asyncio.Event` and
  `loop.add_signal_handler` (`main.py:35-48`).

## Consequences

**Positive**

- Thousands of mostly-idle bins are cheap: an idle task parked on
  `asyncio.sleep` costs far less than a thread or process.
- No shared-state locking: all tasks run cooperatively on one thread, so the
  in-memory registry and per-bin state need no mutexes.
- Clean, deterministic shutdown: cancel every task, await it, dispose resources
  under explicit timeouts (`main.py:52-68`).
- Matches the async I/O stack (`aiokafka`, `asyncpg`) end-to-end.

**Negative / trade-offs**

- **No CPU parallelism.** A single event loop uses one core; any CPU-heavy
  simulation added later would block all bins. The current `_simulate` math is
  cheap, so this is acceptable today.
- **Blocking calls are hazardous.** Introducing synchronous I/O (a blocking DB
  driver, `time.sleep`, `requests`) would stall every bin. Contributors must
  keep the loop non-blocking (noted in [contributing.md](../contributing.md)).
- **Single-process scaling ceiling.** Scaling beyond one process needs bin
  partitioning across instances, which is not implemented
  (see [operations.md](../operations.md#scaling)).
- Platform nuance: signal handling differs on Windows, handled explicitly
  (`main.py:42-48`).

## Related

- [simulation-engine.md](../simulation-engine.md),
  [architecture.md](../architecture.md#concurrency-what-is-async-vs-sync).
