# 02_Kafka Topics: The Gate

### **Overview**

The Kafka topic acts as the persistent, fault-tolerant buffer between the Python Producer and the Spark Consumer. It ensures that data is stored safely even if the downstream Spark cluster experiences downtime.

---

### **Topic Specifications**

For Version 1.0, the topic is configured to balance performance and reliability.

- **Topic Name:** `stream-gate-v1`
- **Partition Count:** **3**
    - *Rationale:* This allows up to 3 Spark executors to read data in parallel. It provides a baseline for scalability without over-complicating the initial cluster load.
- **Replication Factor:** **1** (Development/Local) / **3** (Production)
    - *Rationale:* In production, a factor of 3 ensures that even if two brokers fail, the "Gate" remains open and data is not lost.

---

### **Configuration Parameters**

| **Property** | **Value** | **Description** |
| --- | --- | --- |
| `retention.ms` | `604800000` | **7 Days.** Data remains in the Gate for one week before being purged. |
| `cleanup.policy` | `delete` | Discards old data once the retention period or size limit is reached. |
| `max.message.bytes` | `1048576` | **1MB.** Standard limit for JSON payloads to prevent "jumbo" messages from slowing the cluster. |
| `compression.type` | `producer` | Respects the `snappy` compression sent by the Python Producer. |

---

### **Partitioning Strategy**

In the **Stream Gate** pipeline, we utilize **Round-Robin** partitioning.

- **How it works:** Since the Producer sends messages without a specific "Key," Kafka distributes the JSON payloads evenly across all 3 partitions.
- **Benefit:** This prevents "Hot Partitions" (where one partition is overloaded) and ensures that the Spark Consumer can process the data with a perfectly balanced load.

### **Monitoring & Health**

To ensure the Gate is functioning correctly, the team monitors:

- **Consumer Lag:** The gap between the latest message in Kafka and the last message processed by Spark.
- **Under-Replicated Partitions:** (Production only) Signals if a broker is down or struggling.

---

### **The Lifecycle of a Message**

1. **Append:** The Python Producer appends a JSON string to the end of a partition.
2. **Offset Assignment:** The message is assigned a unique, sequential ID (Offset).
3. **Persistence:** The message is written to disk.
4. **Read:** Spark requests messages starting from the last offset it successfully processed.