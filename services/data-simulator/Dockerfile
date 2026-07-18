# ===========================
# Base Stage
# ===========================
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app


# ===========================
# Test Stage
# ===========================
FROM base AS test

COPY requirements.txt .
COPY requirements-dev.txt .

RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# This will run only when building the test stage
RUN pytest


# ===========================
# Runtime Stage
# ===========================
FROM base AS runtime

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "src/main.py"]