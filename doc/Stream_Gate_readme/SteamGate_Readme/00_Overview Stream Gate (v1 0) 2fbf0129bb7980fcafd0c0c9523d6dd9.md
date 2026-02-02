# 00_Overview: Stream Gate (v1.0)

**Stream Gate** is a real-time data ingestion pipeline designed to bridge external JSON data sources with our core analytics engine. Version 1.0 focuses on establishing a **high-throughput, decoupled architecture** that allows for independent scaling of producers and consumers without the initial overhead of centralized data governance.

---

**Core Objectives**

- **Decoupling:** Separate the data generation logic (Python) from the data processing logic (Spark) via Apache Kafka.
- **Resilience:** Utilize Kafka’s partitioning and persistence to ensure data is buffered and retrievable in case of downstream failures.
- **Velocity:** Enable "Schema-on-Read" processing to allow the team to iterate quickly on data structures without requiring infrastructure changes.

---

**Architecture Summary**

The pipeline follows a linear flow across three primary layers:

1. **Ingestion Layer (The Producer):** A lightweight Python service that serializes incoming data from upstream sources into JSON format.
2. **Messaging Layer (The Gate):** An Apache Kafka cluster acting as the central hub. It manages traffic through a dedicated topic partitioned for parallelism.
3. **Processing Layer (The Consumer):** An Apache Spark application utilizing **Structured Streaming** to consume, parse, and transform the raw JSON stream.

---

**System Design Assumptions**

- **Format:** All messages transmitted through Stream Gate are raw JSON strings.
- **Governance:** Version 1.0 does not utilize a Schema Registry; data contracts are managed manually between the Producer and Consumer teams.
- **Consistency:** The system is configured for "At-Least-Once" delivery to prioritize data completeness.

---

### **High-Level Data Flow:**

`Upstream Source` → `Python Producer` → **`Kafka (Stream Gate Topic)`** → `Spark Structured Streaming` → `Downstream Sink`