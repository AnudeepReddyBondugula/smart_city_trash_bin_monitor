# Docker Compose

The root `docker-compose.yml` runs three services:

- `postgres`: PostgreSQL 15 with persistent `postgres_data` and host port 5433.
- `kafka`: Confluent Kafka 7.4.1 in single-node KRaft mode, exposed on 9092.
- `data_simulator`: the Python simulator built from `services/data-simulator/`.

Both PostgreSQL and the simulator read
`services/data-simulator/.env.docker`. Create it from the tracked template:

```bash
test -f services/data-simulator/.env.docker || \
  cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
```

## Start and initialize

```bash
docker compose up -d postgres kafka
docker compose build data_simulator
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose up -d --force-recreate data_simulator
```

`docker compose restart data_simulator` does not adopt a newly built image.
Use `up -d --force-recreate` after source or migration changes.

## Inspect and stop

```bash
docker compose ps
docker compose logs -f data_simulator
docker compose down
```

`docker compose down -v` also deletes PostgreSQL data and should only be used
when a full reset is intended.
