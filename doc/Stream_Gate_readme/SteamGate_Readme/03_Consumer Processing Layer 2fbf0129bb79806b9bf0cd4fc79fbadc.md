# 03_Consumer: Processing Layer

### **Overview**

The Consumer is the "brains" of the pipeline. It uses **Spark Structured Streaming** to provide a high-level, declarative API for processing data. Even though our data is stored as raw JSON in Kafka, Spark allows us to treat the stream as an unbounded table that we can query and transform.

### **Technical Stack**

- **Framework:** Apache Spark 3.x
- **Module:** Structured Streaming
- **Language:** Python (PySpark)
- **Strategy:** Schema-on-Read

### **The "Schema-on-Read" Strategy**

Since **Stream Gate V1** operates without a Schema Registry, the Spark Consumer must define the data structure manually.

1. **Raw Input:** Spark reads the Kafka messages as a two-column table: `key` and `value` (both in binary).
2. **Casting:** The binary `value` is cast into a `STRING`.
3. **Parsing:** Spark uses a pre-defined `StructType` (the schema) to parse that JSON string into multiple, typed columns.

---

### **Consumer Configuration**

| **Parameter** | **Value** | **Reason** |
| --- | --- | --- |
| `startingOffsets` | `earliest` | Ensures no data is missed if the consumer starts late. |
| `failOnDataLoss` | `false` | Prevents the stream from crashing if Kafka metadata is briefly out of sync. |
| `maxOffsetsPerTrigger` | `1000` | Controls the "micro-batch" size to prevent memory spikes. |
| `checkpointLocation` | `/mnt/checkpoints/stream-gate/` | **Critical.** Stores the current offset so Spark can resume exactly where it left off after a restart. |

---

### **Implementation Workflow**

**1. Connection**
Spark connects to the `stream-gate-v1` topic using the Kafka connector.

**2. Schema Application**
The developer defines a `StructType` matching the JSON blueprint from the Producer.
*Example: `field("event_id", StringType), field("timestamp", TimestampType)...`*

**3. Transformation**
Once parsed, the data is treated as a standard DataFrame. We can filter, aggregate, or mask sensitive fields before the data reaches its final destination.

**4. The Sink (Output)**
The final data is written to the **Downstream Sink**.

- **Mode:** `Append` (Only new records are added).
- **Trigger:** `processingTime='10 seconds'` (Defines how often Spark checks Kafka for new data).

---

### **Monitoring the Stream**

The team uses **Spark UI** to monitor the **Batch Duration** and **Input Rate**. If the input rate from the Python Producer exceeds Spark's processing capacity, we increase the number of executors or partitions in the Gate.