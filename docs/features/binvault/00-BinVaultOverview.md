## What is BinVault?

**BinVault** is the **analytical storage layer** of the Smart Bin Monitoring System.

It is responsible for **persisting processed bin telemetry and analytics outputs** produced by the streaming and batch processing layers. BinVault stores **cleaned, structured, query-ready data** that can be efficiently accessed by APIs, dashboards, and analytical workloads.

BinVault is intentionally designed as a **read-optimized data store**, not a streaming system and not a processing engine.

## Why BinVault Exists

Raw telemetry streams are not suitable for direct consumption by dashboards or business users.

BinVault exists to:

- Persist historical telemetry and aggregates
- Support time-series and analytical queries
- Enable fast, reliable access for APIs
- Decouple storage concerns from processing concerns
- Provide a **single source of analytical truth**

In real-world data platforms, this role is fulfilled by data warehouses, analytical databases, or lakehouse systems. In this project, BinVault fulfills that role using **PostgreSQL** for clarity, learning value, and local deployment simplicity.

## Role in Smart Bin Monitoring System

Within the overall system, BinVault sits **downstream of Spark and upstream of APIs**.

Its role is to:

- Receive processed outputs from Spark
- Store structured analytical datasets
- Serve data to REST APIs and dashboards
- Enable historical analysis and drill-downs

BinVault does **not** ingest raw events directly from Kafka and does **not** perform stream processing.

## In Scope

BinVault is responsible for:

- Storing curated telemetry data
- Storing aggregated and derived metrics
- Supporting time-based and ward/bin-level queries
- Acting as the analytical backend for APIs
- Preserving historical data for trend analysis

## Out of Scope

BinVault explicitly does **not** handle:

- ❌ Event ingestion from Kafka
- ❌ Stream processing or windowing
- ❌ Real-time alerting
- ❌ Business rule evaluation
- ❌ Visualization logic
- ❌ API request handling

These responsibilities belong to Spark, API services, or the dashboard layer.

## Design Boundary (Explicit)

BinVault follows a strict contract:

> Store analytical data and serve it efficiently — nothing more.
> 

This ensures:

- Clear ownership of responsibilities
- Simplified debugging and evolution
- Easy replacement with another analytical store in the future

## Summary

BinVault is the **analytical memory** of the Smart Bin Monitoring System.

It transforms ephemeral streams into durable, queryable datasets, enabling dashboards and decision-making while remaining deliberately simple, predictable, and storage-focused.