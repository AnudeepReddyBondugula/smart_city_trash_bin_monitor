---
name: kafka
description: >
  Load for KafkaClient, telemetry publishing, message keys and JSON shape,
  connection retries, topics, or KRaft Compose configuration.
---

# Kafka

Two topics, created explicitly by the `kafka_init` Compose service rather than
auto-created — auto-creation gives one partition, which pins the whole stream to
a single Spark task.

| Topic | Partitions | Written by | Read by |
|---|---|---|---|
| `smartbin-telemetry-v1` | 12 | data-simulator | stream-processor |
| `smartbin-telemetry-dlq` | 3 | stream-processor | operators |

The data simulator only produces. `KafkaClient` owns a module-level
`AIOKafkaProducer`; `main.py` starts and stops it, and each `BinSimulator`
publishes through the shared client.

## Contract

- Topic: `settings.KAFKA_TOPIC` (`smartbin-telemetry-v1` in example env files).
- Key: UTF-8 encoded bin ID.
- Value: JSON from `Bin.to_payload()`.
- Fields: bin ID, capacity, fill level, battery level, temperature, latitude,
  longitude, zone, and UTC timestamp. The shape is fixed by
  `contracts/telemetry-v1.json`, which both services assert against; a renamed
  field otherwise reads as nulls on the consumer with nothing failing.
- The key matters beyond routing: per-bin ordering across 12 partitions is what
  the stateful operator depends on. Never repartition an existing topic.

Docker connects to `kafka:29092`; native processes connect to
`localhost:9092` through their respective environment files.

## Behavior and limits

- Startup retries Kafka connection ten times, three seconds apart, then raises.
- `send_and_wait` awaits the broker acknowledgement for each message.
- Sends made before startup or sends that raise are logged and dropped; there
  is no producer-side retry queue. The dead-letter topic is a *consumer* concern
  and does not catch these — a message the producer never sent is invisible,
  which weakens dead-device detection.
- `aiokafka.cluster` logging is suppressed to CRITICAL.
- `--from-beginning` replays historical payloads, including records created
  before newer fields existed. Omit it when validating the current schema.

Read two newly produced records:

```bash
docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic smartbin-telemetry-v1 \
  --max-messages 2 --timeout-ms 20000
```
