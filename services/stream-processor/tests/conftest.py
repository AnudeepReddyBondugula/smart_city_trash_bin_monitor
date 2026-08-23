import json
import os
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]

# Spark's Python workers are separate processes and inherit only the
# environment, not pytest's import configuration. Without src on their path they
# cannot import the module holding the function they were asked to run, and fail
# with a bare ModuleNotFoundError from inside a Spark stack trace. The image
# sets the same thing through PYTHONPATH.
os.environ["PYTHONPATH"] = os.pathsep.join(
    filter(None, [str(SERVICE_ROOT), str(SERVICE_ROOT / "src"), os.environ.get("PYTHONPATH")])
)

# Set dummy environment variables for pydantic settings validation during tests
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
os.environ.setdefault("KAFKA_TOPIC", "smartbin-telemetry-v1")


@pytest.fixture(scope="session")
def spark():
    """A local Spark session shared by every test that needs one.

    Starting a session costs seconds, so it is built once per run. One core and
    one shuffle partition, because these tests process a handful of rows and the
    default two hundred partitions would spend all their time on scheduling.

    The pipeline's transformations are plain DataFrame functions, which behave
    identically on a batch DataFrame and a streaming one. Testing them on batch
    data keeps the tests fast and readable while exercising the real code.
    """
    from pyspark.sql import SparkSession

    from session import ensure_worker_interpreter

    # Same call the service makes, for the same reason: without it Spark's
    # workers launch under the system python rather than this virtual
    # environment, and every pandas-based operator fails on a missing import.
    ensure_worker_interpreter()

    session = (
        SparkSession.builder.appName("stream-processor-tests")
        .master("local[1]")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")

    yield session

    session.stop()


@pytest.fixture
def telemetry():
    """A factory for well-formed telemetry payloads.

    Defaults describe a healthy, half-full bin; pass overrides for the field
    under test so each test states only what it is actually about.
    """

    def build(**overrides):
        payload = {
            "bin_id": "BIN-TEST-01",
            "capacity": 100.0,
            "current_fill_level": 50.0,
            "battery_level": 80.0,
            "temperature": 25.0,
            "latitude": 17.4,
            "longitude": 78.5,
            "zone": "CENTRAL",
            "timestamp": "2026-08-22T10:00:00+00:00",
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def kafka_records(spark):
    """Turn telemetry payloads into a DataFrame shaped like the Kafka source.

    Accepts dicts, or raw strings for the messages that are meant to be
    unparseable.
    """

    def build(*payloads):
        rows = [
            (
                bytearray(
                    (
                        payload if isinstance(payload, str) else json.dumps(payload)
                    ).encode()
                ),
                "smartbin-telemetry-v1",
                0,
                index,
            )
            for index, payload in enumerate(payloads)
        ]
        return spark.createDataFrame(rows, "value binary, topic string, partition int, offset long")

    return build
