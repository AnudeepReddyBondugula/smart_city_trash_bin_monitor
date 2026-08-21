# Configuration Loading

```text
process environment
  → Settings validates required POSTGRES_* and KAFKA_* values
  → get_settings() caches one Settings instance per process
  → DATABASE_URL is computed with the asyncpg driver
  → database, Alembic, Kafka, simulator, and seed code consume settings
```

Docker Compose injects `services/data-simulator/.env.docker`. Native scripts
load `.env.local`. The application does not load dotenv files by itself.
