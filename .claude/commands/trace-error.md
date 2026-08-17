---
description: Locate the likely source of an error using this repo's logging patterns.
argument-hint: <error message or stack trace>
---

# /trace-error <error message or stack trace>

Given an error message or stack trace (`$ARGUMENTS`), locate the likely source
using this service's actual logging and error-handling patterns.

## What this repo's error handling looks like (verified)

- **Logging setup:** `src/logging_config.py:12` `setup_logging()`. Format is
  `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`
  (`logging_config.py:21-23`). The `%(name)s` field is the module logger
  (`logging.getLogger(__name__)`), so it points straight at the file.
- **Log sinks:** color console (`logging_config.py:37-38`) **and** rotating file
  `logs/simulator.log` (20MB × 5, `logging_config.py:41-46`). Check both.
- **Kafka errors are swallowed & logged, not raised:**
  - producer not started → `logger.error(... dropping telemetry ...)`
    (`src/kafka_producer.py:53-55`).
  - send failure → `logger.error(f"Failed to send telemetry for {bin_id}: {e}")`
    (`src/kafka_producer.py:61-62`).
  - connect retries → `logger.warning("Kafka not ready yet ...")`
    (`src/kafka_producer.py:33-35`); final failure **raises**
    (`src/kafka_producer.py:42-44`).
- **Shutdown cleanup errors** are caught and logged as warnings, per step
  (`src/main.py:53-66`).
- **Simulator cancellation** logs a warning (`src/bin_simulator.py:108-111`).
- **Config errors** surface as pydantic `ValidationError` at first
  `get_settings()` (`src/config.py:33`) — usually a missing env var.
- **Seed errors** are caught and `print`ed, not logged (`src/seed.py:45-46`).

## Steps

1. Read `$ARGUMENTS`. Extract the distinctive substring (a message, exception
   type, or `bin_id`).
2. `grep -rn` that substring under `services/data-simulator/src` to find the
   emitting line. Message templates use `%s`/f-strings, so search on the static
   part (e.g. `"Failed to send telemetry"`, `"Kafka not ready yet"`,
   `"already stopped"`).
3. Before exploring further, check `.claude/breadcrumbs/_INDEX.md`'s Quick
   navigation table for a row matching the symptom — it points straight at the
   right `DEBUG.md`.
4. If it's a bare Python traceback, map the top in-repo frame to `file:line` and
   read the surrounding function; cross-reference the matching breadcrumb
   folder in `.claude/breadcrumbs/`.
5. Map to a likely cause using the patterns above (e.g. "dropping telemetry" ⇒
   producer never started ⇒ check the `startup-and-telemetry` flow / Kafka
   reachability).
6. Report: the emitting `file:line`, the probable root cause, and the next check
   to run (logs to inspect, env var to verify, or breadcrumb to follow).

## Related

- `.claude/skills/kafka/SKILL.md`, `.claude/skills/config/SKILL.md`.
- `.claude/skills/follow-breadcrumb/SKILL.md`.
- `.claude/breadcrumbs/startup-and-telemetry/DEBUG.md`, `.claude/breadcrumbs/_INDEX.md`.
