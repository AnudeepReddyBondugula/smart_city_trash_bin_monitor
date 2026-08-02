# ADR 003: Use Apache Kafka for telemetry streaming

- **Status:** Accepted (reflects current implementation)
- **Source note:** *Inferred from the codebase, not an original design record.*
  Reconstructed from code, `docker-compose.yml`, and dependencies; code-tied
  points are cited.

---

## Context

The simulator continuously emits per-bin telemetry snapshots (fill level,
battery, location, timestamp) that downstream consumers — dashboards,
alerting, analytics — will want to read independently and in real time. The
producer generates one message per bin per `SIMULATION_INTERVAL`; the volume
scales with the fleet size.

Requirements implied by the design:

- A **decoupled** transport so the simulator does not know or wait on
  consumers.
- **Per-bin ordering** (a bin's snapshots should stay in order).
- Real-time fan-out to multiple/independent consumers.
- Full snapshots each tick, so occasional loss is tolerable
  (see [kafka.md](../kafka.md#delivery-guarantees-as-actually-configured)).

## Decision

Use **Apache Kafka** (Confluent `cp-kafka:7.4.1`, **KRaft mode** — no
ZooKeeper) as the streaming backbone, with the simulator acting as a
**producer only**.

Evidence in code / config:

- `kafka` service in `docker-compose.yml` with `KAFKA_PROCESS_ROLES:
  'broker,controller'` (KRaft), internal listener `kafka:29092` and host
  listener `localhost:9092`.
- `KafkaClient` wrapping `AIOKafkaProducer` (`kafka_producer.py`), JSON value
  serializer, publishing to `KAFKA_TOPIC` (`smartbin-telemetry-v1`) **keyed by
  `bin_id`** (`kafka_producer.py:58-59`).
- `aiokafka` in `requirements.txt`.
- No consumer anywhere in `src/` — the service only produces.

## Consequences

**Positive**

- **Producer/consumer decoupling:** the simulator publishes and moves on; any
  number of consumers can subscribe without changing it.
- **Per-bin ordering:** keying by `bin_id` routes each bin's messages to one
  partition, preserving order per bin.
- **Real-time, replayable log:** consumers can read live or from history and can
  join/leave independently.
- **KRaft simplifies ops:** no ZooKeeper to run — a single container is the
  whole broker.
- The async producer (`aiokafka`) fits the asyncio model
  (see [ADR 001](001-asyncio.md)).

**Negative / trade-offs**

- **Operational weight** of a broker for a simulator — heavier than, say, a
  simple queue or direct DB writes. Justified by the real-time fan-out and
  ordering needs.
- **Best-effort delivery as configured:** default `acks`, no idempotence, no
  producer retries; failed sends are logged and dropped
  (`kafka_producer.py:61-62`). Acceptable because each tick re-sends full state,
  but not suitable if exactly-once/durable delivery is later required.
- **Single-node, RF 1** in the compose setup — no broker HA
  (`KAFKA_*_REPLICATION_FACTOR: 1`).
- **Topic auto-creation** is relied upon rather than explicit provisioning
  (see [kafka.md](../kafka.md#topics)). *(TODO: confirm intended.)*
- **Schema is implicit** (plain JSON, no schema registry) — consumers must track
  the payload shape out of band; the `-v1` topic suffix is the only versioning
  signal.

## Alternatives considered (inferred)

- **Direct DB writes of telemetry:** rejected — would make Postgres a
  high-write time-series sink and couple producers to consumers; contradicts the
  explicit "telemetry is not persisted to the DB" design.
- **A simple message queue (e.g. RabbitMQ):** weaker on replay, multi-consumer
  fan-out, and partition-based ordering guarantees for a streaming workload.

## Related

- [kafka.md](../kafka.md), [architecture.md](../architecture.md),
  [simulation-engine.md](../simulation-engine.md).
