---
name: kafka
description: >
  Load for KafkaClient, telemetry publishing, message keys and JSON shape,
  connection retries, topics, or KRaft Compose configuration.
---

# Kafka Producer

The data simulator only produces messages. `KafkaClient` owns a module-level
`AIOKafkaProducer`; `main.py` starts and stops it, and each `BinSimulator`
publishes through the shared client.

## Contract

- Topic: `settings.KAFKA_TOPIC` (`smartbin-telemetry-v1` in example env files).
- Key: UTF-8 encoded bin ID.
- Value: JSON from `Bin.to_payload()`.
- Fields: bin ID, capacity, fill level, battery level, temperature, latitude,
  longitude, zone, and UTC timestamp.

Docker connects to `kafka:29092`; native processes connect to
`localhost:9092` through their respective environment files.

## Behavior and limits

- Startup retries Kafka connection ten times, three seconds apart, then raises.
- `send_and_wait` awaits the broker acknowledgement for each message.
- Sends made before startup or sends that raise are logged and dropped; there
  is no retry queue or dead-letter topic.
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
