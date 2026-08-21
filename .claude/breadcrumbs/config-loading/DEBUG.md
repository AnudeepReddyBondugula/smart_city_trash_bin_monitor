# Configuration Loading — Debug Guide

| Symptom | Check |
|---|---|
| Pydantic reports missing fields | Confirm every required PostgreSQL and Kafka variable is exported before importing application modules. |
| Docker uses unexpected values | Check `services/data-simulator/.env.docker` and recreate the container. |
| Native process uses unexpected values | Source `.env.local` before starting Python. |
| Environment edit has no effect | Restart the process because `get_settings()` is cached. |
| Host cannot reach PostgreSQL | Use host port 5433; containers use `postgres:5432`. |

The application intentionally has no built-in defaults for credentials,
database identity, Kafka bootstrap servers, or Kafka topic.
