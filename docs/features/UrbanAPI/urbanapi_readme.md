# UrbanAPI Design

> **Status: planned.** No UrbanAPI service or routes are implemented in this
> repository. The paths and project structure below are proposals.

Creating APIs for fetching data for the frontend.

Tech Stack Used:

```
fastapi
uvicorn
sqlalchemy
psycopg2-binary
pydantic
python-jose
passlib==1.7.4
bcrypt==3.2.2
python-multipart
redis
```

API’s going to built are:

`/api_health`

`/ward/latest`

`/wards/wardId/latest`

`/ward/history?hours=24`

`/wards/wardId/history?hours=24`

`/wards/wardID/`

`/ward/risk_analysis_dashboard`

`/ward/risk_analysis/alerts` 

- **Phase 5.1 (Alerts):**
    - `api/alerts.py` → routes
    - `schemas/alerts.py` → response models
    - `services/alerts_service.py` → logic (thresholds, reasons)
    - `db/queries.py` → SQL for risk tables
- **Phase 5.2 (Ward Analytics):**
    - `api/wards.py` → analytics endpoint
    - `schemas/wards.py` → time series, distribution, risk history models
    - `services/wards_service.py` → business logic
- **Phase 5.3 (Data Quality Metrics):**
    - `api/metrics_stream.py` → streaming health endpoint
    - `schemas/metrics.py` → metrics schema
    - `services/metrics_service.py` → compute late %, duplicates, DLQ
- **Phase 5.4 (Observability):**
    - `observability/middleware.py` → structured logs + latency
    - `observability/cache.py` → Redis hit/miss
    - `observability/prometheus.py` → Prometheus metrics
    
    ### Bin Analysis APIs
    
- `GET /bins` → All bins summary
- `GET /bins/{bin_id}` → Single bin detail + risk history
- `GET /wards/{ward_id}/bins/distribution` → Ward-level distribution
- `GET /wards/{ward_id}/bins/critical` → Critical bins in a ward
- `GET /bins/{bin_id}/quality` → Data quality metrics per bin

## FastAPI Project Directory

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI entrypoint (creates app, includes routers, middleware)
│   │
│   ├── api/                   # API route definitions
│   │   ├── __init__.py
│   │   ├── alerts.py          # /alerts/wards endpoint
│   │   ├── wards.py           # /wards/{id}/analytics endpoint
│   │   ├── metrics_stream.py  # /metrics/stream endpoint
│   │   └── health.py          # /health or /ping endpoint
│   │
│   ├── core/                  # Core config and utilities
│   │   ├── __init__.py
│   │   ├── config.py          # Settings (env vars, thresholds, DB URL)
│   │   ├── logging.py         # Structured logging setup
│   │   └── security.py        # Auth, cookies, CORS
│   │
│   ├── db/                    # Database layer
│   │   ├── __init__.py
│   │   ├── session.py         # Connection pooling (asyncpg / SQLAlchemy)
│   │   ├── models.py          # ORM models or typed classes
│   │   └── queries.py         # Raw SQL queries / repository functions
│   │
│   ├── schemas/               # Pydantic models (request/response)
│   │   ├── __init__.py
│   │   ├── alerts.py
│   │   ├── wards.py
│   │   └── metrics.py
│   │
│   ├── services/              # Business logic
│   │   ├── __init__.py
│   │   ├── alerts_service.py
│   │   ├── wards_service.py
│   │   └── metrics_service.py
│   │
│   ├── observability/         # Ops & monitoring
│   │   ├── __init__.py
│   │   ├── middleware.py      # Request latency logging
│   │   ├── cache.py           # Redis hit/miss logging
│   │   └── prometheus.py      # /metrics endpoint
│   │
│   └── tests/                 # Unit & integration tests
│       ├── __init__.py
│       ├── test_alerts.py
│       ├── test_wards.py
│       └── test_metrics.py
│
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Backend container definition
├── docker-compose.yml         # Compose file (backend + db + redis)
└── README.md                  # Documentation
