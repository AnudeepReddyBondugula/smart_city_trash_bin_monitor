# 🚮 Smart City Trash Bin Monitor 🏙️

## 📌 Introduction
Smart City Trash Bin Monitor is a **real-time data engineering project** that simulates and processes IoT-enabled trash bin data using a **fault-tolerant streaming architecture**.  
The project focuses on building a **production-grade streaming pipeline** that ingests sensor data, cleans and aggregates it in real time, and stores reliable results for downstream consumption.

This repository currently implements the **core real-time data pipeline** with strong guarantees around **performance, reliability, and maintainability**.

---

## 📖 Project Description
Modern cities generate continuous streams of waste management data from smart bins deployed across wards and zones.  
This project demonstrates how such data can be:

- Ingested in real time
- Validated and cleaned safely
- Processed with **exactly-once semantics**
- Persisted reliably even during failures
- Scaled and maintained using best practices

The emphasis of this project is **data engineering correctness and robustness**, not just data movement.

---

## 🎯 Objectives (Implemented)
- Real-time ingestion of trash bin sensor data
- Safe handling of malformed or invalid events
- Deduplication and late-data handling
- Ward-level aggregation of bin fill levels
- Reliable persistence with retry and recovery
- Environment-driven configuration (Docker-ready)

---

## 🧠 Key Features (Current Implementation)

### ✅ Real-Time Data Ingestion
- Kafka-based ingestion pipeline
- Controlled ingestion rate using `maxOffsetsPerTrigger`
- Separate handling for valid and invalid events

### ✅ Stream Processing with Spark Structured Streaming
- Stateful processing with watermarking
- Deduplication based on business keys
- Windowed aggregations (ward-wise fill levels)
- Exactly-once guarantees using checkpointing

### ✅ Dead Letter Queue (DLQ)
- Invalid or malformed events routed to a dedicated Kafka topic
- DLQ is isolated and does not block the main pipeline
- Full auditability of bad data

### ✅ Fault Tolerance & Recovery
- Safe `foreachBatch` execution
- Database retries with exponential backoff
- Automatic recovery from Spark restarts
- No duplicate writes due to idempotent UPSERTs

### ✅ Performance Optimized
- Batch time reduced from ~20s to ~2–6s
- Optimized Spark parallelism and shuffles
- Batched database writes

### ✅ Maintainable & Configurable
- All infrastructure config externalized via environment variables
- Schema versioning for forward compatibility
- Clean modular Spark job structure

---

## 🏗️ Current Architecture (Implemented)

Data Simulator (Python)
↓
Apache Kafka
├── valid-trash-bin-data
└── invalid-trash-bin-data (DLQ)
↓
Apache Spark Structured Streaming
↓
PostgreSQL (Aggregated Results)

---

## 🧰 Tech Stack (Implemented)

| Layer | Technology |
|-----|-----------|
| Data Simulation | Python |
| Streaming Ingestion | Apache Kafka |
| Stream Processing | Apache Spark Structured Streaming |
| Fault Handling | Kafka Dead Letter Queue |
| Data Storage | PostgreSQL |
| Containerization | Docker & Docker Compose |
| Language | Python |
| Observability | Spark StreamingQueryListener |

---

## 📂 Project Structure (Current)

smart-city-trash-bin-monitor/
│
├── simulator/ # Trash bin data simulator
├── spark-apps/ # Spark Structured Streaming job
│ ├── kafka_to_postgres.py
│ ├── config.py
│ └── Dockerfile
│
├── docker-compose.yml # Kafka, Spark, Postgres setup
├── .env.example # Environment configuration template
└── README.md

---

## 🚀 How to Run (Current)

- git clone (https://github.com/AbhiSathya/smart_city_trash_bin_monitor.git)

- cd smart-city-trash-bin-monitor

- docker compose up --build


Spark will:

- Consume live Kafka data

- Process valid events

- Route invalid events to DLQ

- Persist aggregated results into PostgreSQL

---

## 🧪 Failure Scenarios Handled
✅ Invalid JSON → routed to DLQ

✅ Duplicate events → deduplicated

✅ Postgres temporarily down → retried safely

✅ Spark restart → resumes from checkpoint

✅ Late data → handled via watermarking

---

## 🔮 Planned Enhancements (Not Implemented Yet)
The following features are intentionally not implemented yet and are planned as future phases:

🔲 Backend API (FastAPI) for querying bin status

🔲 Dashboard (Map & charts for monitoring)

🔲 Alerting system (overflow thresholds)

🔲 Route optimization & prediction logic

🔲 Historical batch analytics

🔲 Airflow-based orchestration