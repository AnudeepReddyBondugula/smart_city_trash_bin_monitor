#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Ensuring infrastructure is running..."
docker-compose -f ../../docker-compose.infra.yml up -d

echo "Waiting for PostgreSQL to be ready..."
while ! docker exec smartbin_postgres pg_isready -U postgres; do
    sleep 2
done

echo "Infrastructure is ready."
echo "Starting simulator..."
cd ..
PYTHONPATH=. python src/main.py
