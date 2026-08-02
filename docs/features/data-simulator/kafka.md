# Kafka

The Data Simulator is a **Kafka producer only** — it publishes telemetry and
consumes nothing. Messaging is handled by `aiokafka`'s `AIOKafkaProducer`,
wrapped in a singleton `KafkaClient` (`src/kafka_producer.py`). Rationale for
choosing Kafka: [decisions/003-kafka.md](decisions/003-kafka.md).

---

## Broker

Defined in `docker-compose.yml` as service `kafka`
(`confluentinc/cp-kafka:7.4.1`) running in **KRaft mode** (`KAFKA_PROCESS_ROLES:
'broker,controller'`) — no ZooKeeper. Single-node, replication factor 1
throughout (`KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1`,
`KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1`).

### Listeners

| Listener | Address | Used by |
| --- | --- | --- |
| `PLAINTEXT` (internal) | `kafka:29092` | Other containers on the compose network (the simulator) |
| `PLAINTEXT_HOST` (external) | `localhost:9092` | Tools on the host machine |
| `CONTROLLER` | `kafka:29093` | KRaft controller quorum |

So the simulator container connects to `kafka:29092`
(`.env.docker` → `KAFKA_BOOTSTRAP_SERVERS=kafka:29092`), while host tools such
as `kafka-console-consumer` or a natively-run simulator use `localhost:9092`
(`.env.local.example`).

---

## Topics

| Topic | Direction | Where set |
| --- | --- | --- |
| `smartbin-telemetry-v1` | **Produced** | `KAFKA_TOPIC` env var (`.env.docker`, `.env.local.example`) |

The service **consumes no topics** — there is no consumer, no consumer group,
and no `aiokafka.AIOKafkaConsumer` anywhere in `src/`.

> **Topics are not pre-declared.** `docker-compose.yml` does not create the
> topic, and the producer does not explicitly create it either. With the default
> Confluent broker settings, `smartbin-telemetry-v1` is auto-created on first
> produce (single partition, RF 1). *(TODO: confirm with team whether relying on
> auto-create is intended vs. an explicit topic-provisioning step.)*

---

## Message schema

The producer serializes the dict returned by `Bin.to_payload()` as UTF-8 JSON.
Full field list and rounding rules: see
[simulation-engine.md](simulation-engine.md). Example value:

```json
{
  "bin_id": "BIN-1A2B3C4D-X",
  "capacity": 100.0,
  "current_fill_level": 42.37,
  "battery_level": 98.61,
  "latitude": 40.1234,
  "longitude": -73.9876,
  "timestamp": "2026-08-02T12:34:56.789012+00:00"
}
```

- **Value:** `json.dumps(payload).encode("utf-8")` via the producer's
  `value_serializer` (`kafka_producer.py:25`).
- **Key:** the `bin_id`, encoded as UTF-8 bytes —
  `key=bin_id.encode("utf-8")` (`kafka_producer.py:59`). Keying by `bin_id`
  means all telemetry for a given bin lands on the same partition, preserving
  per-bin ordering. Verified by `tests/test_kafka_producer.py:79-99`.
- **Headers / schema registry:** none. Plain JSON, no Avro/Protobuf, no schema
  registry configured.

The `-v1` suffix in the topic name is the versioning convention — a breaking
payload change would move to a new topic (e.g. `smartbin-telemetry-v2`).

---

## Producer setup

`KafkaClient.start()` (`src/kafka_producer.py:15-44`):

```python
self.producer = AIOKafkaProducer(
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)
await self.producer.start()
```

- **Connection retries:** up to 10 attempts, 3 seconds apart. On each failed
  attempt a partially-constructed producer is stopped (errors swallowed) before
  retrying. After 10 failures it raises
  `"Could not connect to Kafka on {servers} after multiple retries"`
  (`kafka_producer.py:16-44`, tested at `test_kafka_producer.py:29-77`). This
  tolerates the broker still starting up when the simulator boots.
- **Singleton:** `kafka_client = KafkaClient()` at module scope
  (`kafka_producer.py:65`) — the same instance is imported by `main.py` and
  `bin_simulator.py`.

---

## Delivery guarantees (as actually configured)

Send path — `KafkaClient.send_telemetry()` (`kafka_producer.py:51-62`):

```python
await self.producer.send_and_wait(
    topic=settings.KAFKA_TOPIC, value=payload, key=bin_id.encode("utf-8")
)
```

- **`send_and_wait`** waits for the broker acknowledgement before returning, so
  each publish is synchronous from the caller's perspective (no fire-and-forget
  batching gap left unresolved before the next tick).
- **`acks` is not set explicitly**, so `aiokafka`'s default applies
  (`acks=1` — leader acknowledgement). With single-node RF 1 there are no
  followers regardless.
- **No retries/idempotence configured** on the producer (`enable_idempotence`,
  `acks="all"`, transactions are all unset). Effective guarantee is roughly
  **at-most-once from the application's point of view**: on a send failure the
  exception is caught, an error is logged, and the message is **dropped** — the
  loop moves on rather than retrying (`kafka_producer.py:61-62`).
- **If the producer was never started**, `send_telemetry` logs
  `"Kafka producer is not started; dropping telemetry for {bin_id}"` and returns
  without raising (`kafka_producer.py:52-56`, tested at
  `test_kafka_producer.py:101-109`).

> **Net effect:** telemetry is best-effort. Because the simulator regenerates
> state every `SIMULATION_INTERVAL` seconds and emits a full snapshot each time,
> a dropped message is self-healing on the next tick — losing one payload is not
> critical for this workload. If stronger guarantees are needed, set
> `acks="all"`, `enable_idempotence=True`, and add producer-side retries.

---

## Shutdown

`KafkaClient.stop()` calls `producer.stop()` (which flushes pending messages and
closes the connection) and logs `"Kafka producer stopped"`; it is a safe no-op
if no producer was started (`kafka_producer.py:46-49`). Called from `main.py`
during graceful shutdown under a 5-second timeout.

---

## Consuming the stream (for verification)

From the host, against the external listener:

```bash
docker exec -it smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic smartbin-telemetry-v1
```

More verification commands: [operations.md](operations.md).

---

## Related documents

- [simulation-engine.md](simulation-engine.md) — how payloads are generated.
- [configuration.md](configuration.md) — `KAFKA_*` env vars.
- [decisions/003-kafka.md](decisions/003-kafka.md) — why Kafka.
