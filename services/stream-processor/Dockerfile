# ===========================
# Base Stage
# ===========================
# The build context is the repository root, not this directory, so the shared
# telemetry contract can be copied in. Both services build their view of the
# payload from that one file.
FROM python:3.11-slim-bookworm AS base

WORKDIR /app

# Spark runs on the JVM even when driven from Python, and local mode still
# starts one in-process. Spark 3.5 supports Java 8, 11 and 17 - not 21 - which
# is why the base image is pinned to bookworm; trixie dropped the 17 packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app:/app/src
# JAVA_HOME is deliberately unset: Spark falls back to java on PATH, which
# avoids hardcoding a path that differs between amd64 and arm64.

COPY services/stream-processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The Kafka connector, baked in rather than resolved by --packages at submit
# time. Resolving at submit time means the container needs Maven Central to
# start, so a slow repository becomes a service that will not boot.
#
# These versions are not free choices: the connector must match the Spark
# version exactly, and kafka-clients must match what that connector was built
# against.
ARG SPARK_VERSION=3.5.3
ARG SCALA_VERSION=2.12
ARG KAFKA_CLIENTS_VERSION=3.4.1
ARG COMMONS_POOL2_VERSION=2.11.1

RUN JARS=$(python -c "import pyspark, pathlib; print(pathlib.Path(pyspark.__file__).parent / 'jars')") && \
    BASE=https://repo1.maven.org/maven2 && \
    curl -fsSL -o "$JARS/spark-sql-kafka-0-10_${SCALA_VERSION}-${SPARK_VERSION}.jar" \
      "$BASE/org/apache/spark/spark-sql-kafka-0-10_${SCALA_VERSION}/${SPARK_VERSION}/spark-sql-kafka-0-10_${SCALA_VERSION}-${SPARK_VERSION}.jar" && \
    curl -fsSL -o "$JARS/spark-token-provider-kafka-0-10_${SCALA_VERSION}-${SPARK_VERSION}.jar" \
      "$BASE/org/apache/spark/spark-token-provider-kafka-0-10_${SCALA_VERSION}/${SPARK_VERSION}/spark-token-provider-kafka-0-10_${SCALA_VERSION}-${SPARK_VERSION}.jar" && \
    curl -fsSL -o "$JARS/kafka-clients-${KAFKA_CLIENTS_VERSION}.jar" \
      "$BASE/org/apache/kafka/kafka-clients/${KAFKA_CLIENTS_VERSION}/kafka-clients-${KAFKA_CLIENTS_VERSION}.jar" && \
    curl -fsSL -o "$JARS/commons-pool2-${COMMONS_POOL2_VERSION}.jar" \
      "$BASE/org/apache/commons/commons-pool2/${COMMONS_POOL2_VERSION}/commons-pool2-${COMMONS_POOL2_VERSION}.jar"


# ===========================
# Test Stage
# ===========================
FROM base AS test

COPY services/stream-processor/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY contracts/ ./contracts/
COPY services/stream-processor/ .

RUN pytest


# ===========================
# Runtime Stage
# ===========================
FROM base AS runtime

COPY contracts/ ./contracts/
COPY services/stream-processor/ .

CMD ["python", "src/main.py"]
