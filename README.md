# Smart City Trash Bin Monitor

A real-time data pipeline and dashboard for monitoring smart city trash bins. This project simulates IoT devices sending trash bin fill-level data, processes it through Apache Kafka and Apache Spark, stores it in a PostgreSQL database, and provides a FastAPI backend and a Next.js frontend to visualize the data.

## Architecture

1. **Simulator (`simulator/`)**: A Python script simulating IoT trash bins. It generates both valid and invalid events and pushes them to Kafka topics.
2. **Kafka (`docker-compose.yml`)**: A message broker that queues the incoming IoT data.
3. **Consumer (`consumer/`)**: A Python consumer that reads from the invalid events topic and logs them to the database for auditing.
4. **Spark (`spark-apps/`)**: A PySpark structured streaming application that aggregates valid trash bin events over time windows to calculate average fill levels and risk scores, saving the results to PostgreSQL.
5. **Backend (`backend/api/`)**: A FastAPI application providing REST endpoints for the frontend. It uses SQLAlchemy and Alembic for database migrations.
6. **Frontend (`frontend/`)**: A Next.js application that provides a dashboard for city officials to monitor bin fill levels and receive alerts.

## Prerequisites

- **Docker & Docker Compose**: Ensure you have Docker installed and running on your machine.
- **Node.js 20+**: If you want to run the frontend application locally outside of Docker.

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd smart_city_trash_bin_monitor
   ```

2. **Environment Variables**:
   The project requires a `.env` file in the root directory. You can use the provided `.env` configuration (if available) or create your own based on the `docker-compose.yml` defaults:
   ```env
   DB_NAME=trash_bin_db
   DB_USER=admin
   DB_PASSWORD=admin
   DB_HOST=postgres
   DB_PORT=5432
   KAFKA_BOOTSTRAP_SERVERS=kafka:9092
   VALID_TOPIC=valid-trash-bin-data
   INVALID_TOPIC=invalid-trash-bin-data
   DATA_INTERVAL_SECONDS=10
   ERROR_FREQ=0.2
   CONSUMER_GROUP_ID=trash-bin-consumer-group
   ```

## Running the Project

The entire infrastructure can be brought up using Docker Compose. 
This will spin up Zookeeper, Kafka, PostgreSQL, Redis, the Simulator, the Consumer, the Spark streaming job, and the Backend API.

```bash
docker-compose up -d --build
```

### Running the Frontend

The Next.js frontend is not included in the `docker-compose` stack by default so that it can be actively developed locally. To run the frontend:

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies (requires Node.js 20+):
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
The frontend dashboard will be available at [http://localhost:3000](http://localhost:3000).

### Database Migrations

The FastAPI backend automatically applies database migrations upon startup using Alembic. You do not need to run migrations manually unless you are making changes to the schema.

To create a new migration after modifying the SQLAlchemy models in `backend/api/app/models/db_models.py`:
1. Navigate to the backend API directory:
   ```bash
   cd backend/api
   ```
2. Activate your virtual environment and run Alembic (ensure your DB environment variables point to your local development database):
   ```bash
   export DB_HOST=localhost
   export DB_PORT=5433
   alembic revision --autogenerate -m "Your migration description"
   ```

*Note: The PostgreSQL port is mapped to `5433` on the host machine to prevent conflicts with local instances.*

### Default Users

The initial database seed (`init.sql`) provides the following default users:
- **Admin**: Username: `admin` | Password: `admin`
- **Viewer**: Username: `viewer` | Password: `viewer`

## Services Overview

- **Kafka Broker**: `localhost:9092`
- **PostgreSQL**: `localhost:5433`
- **Redis**: `localhost:6380`
- **Spark Web UI**: [http://localhost:4040](http://localhost:4040)
- **FastAPI Backend (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

## Troubleshooting

- **Containers failing to start due to port conflicts**: Check if you have existing services running on ports `2181` (Zookeeper), `9092` (Kafka), `5433` (Postgres host mapping), `6380` (Redis host mapping), or `8000` (FastAPI).
- **Stale Volumes / KeyErrors**: If you encounter Docker Compose issues related to container recreation or volumes, tear down the environment and remove volumes:
  ```bash
  docker-compose down -v
  docker-compose up -d --build
  ```