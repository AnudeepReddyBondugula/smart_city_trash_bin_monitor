---
name: kafka
description: >
  Load when working on telemetry publishing — the AIOKafkaProducer wrapper, the
  KafkaClient singleton, message format/keys, connection retries, or the Kafka
  broker config in docker-compose. Trigger words: Kafka, producer, AIOKafka,
  telemetry, topic, send_telemetry, KafkaClient, broker, KRaft.
---

# Kafka Producer

The service publishes bin telemetry to Apache Kafka (running in KRaft mode). It
is **produce-only** — nothing in this service consumes.

All paths below are relative to `services/data-simulator/`.

## Key files

- `src/kafka_producer.py` — the entire producer.
  - `KafkaClient` class (`:11`) wraps an `AIOKafkaProducer`.
  - `kafka_client = KafkaClient()` (`:65`) is a module-level **singleton**
    imported everywhere (e.g. `src/main.py:3`,
    `src/simulator/bin_simulator.py:6`).
  - `start()` (`:15`) — retries connecting **10 times**, 3s apart
    (`:16`, `:41`); raises if all fail (`:42-44`).
  - `stop()` (`:46`) — stops the producer if present.
  - `send_telemetry(bin_id, payload)` (`:51`) — the publish call.
- `docker-compose.yml:18-41` — the `kafka` service (confluentinc/cp-kafka 7.4.1,
  KRaft, single node). In-network listener `kafka:29092`, host listener
  `localhost:9092`.

## Message format

`send_telemetry` (`src/kafka_producer.py:58-60`) sends:
- **topic:** `settings.KAFKA_TOPIC` — `smartbin-telemetry-v1`
  (`.env.docker:9`, `.env.local.example:10`).
- **key:** `bin_id` UTF-8 encoded (partitions by bin).
- **value:** the dict from `Bin.to_payload()`, JSON-serialized via
  `value_serializer` (`:25`).

## Connection targets (env-dependent)

- In Docker: `KAFKA_BOOTSTRAP_SERVERS=kafka:29092` (`.env.docker:8`).
- Local/native run: `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`
  (`.env.local.example:9`).

## How to extend safely

- **New topic / event type:** add a method alongside `send_telemetry` rather than
  overloading it; keep the singleton pattern. Pull the topic name from settings,
  never hard-code.
- **Change serialization:** it's set once on the producer at `:25`
  (`json.dumps(...).encode`). Changing it affects every message.
- Always route sends through `kafka_client` (the singleton) so lifecycle
  (`start`/`stop` in `src/main.py`) stays centralized.

## Pitfalls (evidence in code)

- **Telemetry is dropped, not retried, on failure.** If the producer isn't
  started, `send_telemetry` logs an error and returns (`:52-56`). If a send
  raises, it's caught and logged (`:61-62`) — the message is lost and the
  simulation loop continues. There is no dead-letter or backpressure.
- `send_and_wait` (`:58`) awaits broker ack per message; with many bins and a
  slow broker this serializes each bin's loop iteration.
- Startup will **block up to ~30s** (10 retries × 3s) before giving up if Kafka
  is unreachable (`:16`, `:41`).
- `aiokafka.cluster` logs are force-silenced to CRITICAL in
  `src/logging_config.py:52` — don't expect cluster-level chatter in logs.
