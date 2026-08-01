#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=================================================="
echo " Smart City Trash Bin Monitor - Local Development"
echo "=================================================="
echo
echo "This script starts the required infrastructure (PostgreSQL and Kafka)"
echo "using Docker Compose, then runs the Data Simulator locally."
echo
echo "This setup is intended for development, allowing you to:"
echo "  • Debug the application using your IDE"
echo "  • Make code changes without rebuilding Docker images"
echo "  • Use Docker only for infrastructure services"
echo

echo "Starting PostgreSQL and Kafka containers..."
docker compose -f ../../../docker-compose.yml up -d postgres kafka

echo
echo "Waiting for PostgreSQL to become ready..."
while ! docker exec smartbin_postgres pg_isready -U "${POSTGRES_USER:-postgres}" > /dev/null 2>&1; do
    sleep 2
done

echo "✓ PostgreSQL is ready."
echo "✓ Kafka container is running."
echo

echo "Starting the Data Simulator on your local machine..."
cd ..


set -a
source .env.local
set +a

PYTHONPATH=. python src/main.py