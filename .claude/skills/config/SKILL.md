---
name: config
description: >
  Load for Settings, environment files, DATABASE_URL, Docker versus native
  targets, or missing configuration errors.
---

# Configuration

`src/config.py` defines required PostgreSQL and Kafka settings. It also defines
`NUMBER_OF_BINS=100` and `SIMULATION_INTERVAL=5`; only the interval currently
affects runtime simulation.

`DATABASE_URL` is an asyncpg SQLAlchemy URL. `get_settings()` is cached, so
processes must restart after environment changes.

- `.env.local.example`: tracked template and native-development values.
- `.env.local`: private values loaded by native run scripts.
- `.env.docker`: private values injected by Docker Compose.

The application does not load dotenv files itself. Docker uses `postgres:5432`
and `kafka:29092`; host tools use PostgreSQL 5433 and Kafka 9092.

When adding a required setting, update the template, Docker environment, local
scripts if necessary, and `tests/conftest.py`.
