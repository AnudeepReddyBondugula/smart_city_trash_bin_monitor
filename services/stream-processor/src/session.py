"""Spark session and Kafka source construction."""

import logging
import os
import sys

from pyspark.sql import DataFrame, SparkSession

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def ensure_worker_interpreter() -> None:
    """
    Point Spark's Python workers at the interpreter that is driving them.

    Spark launches workers as plain `python3` from PATH, which is not
    necessarily the interpreter running this code. When it is not - inside a
    virtual environment, most obviously - the workers start without pandas or
    pyarrow and every pandas-based operator fails at run time with a bare import
    error from inside a Spark stack trace, a long way from the actual cause.

    Must be set before a session is created; it is read at worker launch.
    """
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)


def build_session(ui_port: int | None = None) -> SparkSession:
    """
    Build the Spark session the streaming queries run in.

    The two settings worth explaining:

    RocksDB state store. Deduplicating over a ten minute watermark at a thousand
    events a second holds several hundred thousand keys, and that is before the
    per-bin state. The default provider keeps all of it on the JVM heap, so
    garbage collection pauses grow with the state until the job stalls. RocksDB
    spills to local disk instead, and changelog checkpointing means a restart
    replays a change log rather than rebuilding every snapshot.

    Local mode. A thousand events a second on one machine does not need a master
    and workers, and skipping the cluster removes three containers and a network
    from the deployment. This is the setting to revisit first when one machine
    measurably runs out - not before.

    Args:
        ui_port:
            Port for the Spark UI. Defaults to ``SPARK_UI_PORT``. The batch job
            passes its own, because it runs alongside the streaming application
            and would otherwise be pushed onto whichever port Spark found free -
            a different address every run, announced by a warning that reads
            like a fault.
    """
    ensure_worker_interpreter()

    if ui_port is None:
        ui_port = settings.SPARK_UI_PORT

    session = (
        SparkSession.builder.appName(settings.SPARK_APP_NAME)
        .master(settings.SPARK_MASTER)
        .config(
            "spark.sql.streaming.stateStore.providerClass",
            "org.apache.spark.sql.execution.streaming.state."
            "RocksDBStateStoreProvider",
        )
        .config(
            "spark.sql.streaming.stateStore.rocksdb.changelogCheckpointing.enabled",
            "true",
        )
        # Local mode defaults to 200 shuffle partitions, which on a handful of
        # cores means hundreds of near-empty tasks per micro-batch and more time
        # spent scheduling than processing.
        .config("spark.sql.shuffle.partitions", "12")
        .config("spark.sql.session.timeZone", "UTC")
        # Bound explicitly so the UI is always at a known address. Left to
        # Spark's default retry, a busy port moves it silently.
        .config("spark.ui.port", str(ui_port))
        .config("spark.ui.portMaxRetries", "0")
        .getOrCreate()
    )

    session.sparkContext.setLogLevel("WARN")

    logger.info(
        "Spark %s session started on %s, UI on port %d",
        session.version,
        settings.SPARK_MASTER,
        ui_port,
    )
    return session


def read_telemetry(session: SparkSession) -> DataFrame:
    """
    Open the raw telemetry stream.

    Returns the Kafka records untouched - key, value and metadata - because the
    cleaning step needs the raw bytes to forward anything unparseable to the
    dead-letter topic. Parsing here would mean a malformed message was already
    lost by the time anyone could act on it.
    """
    return (
        session.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", settings.KAFKA_TOPIC)
        .option("startingOffsets", settings.STARTING_OFFSETS)
        .option("maxOffsetsPerTrigger", settings.MAX_OFFSETS_PER_TRIGGER)
        # A missing offset means the retention window passed while the job was
        # down. Failing there requires a human to restart a job that cannot do
        # anything but skip ahead; carrying on loses the same data either way
        # and keeps the pipeline alive.
        .option("failOnDataLoss", "false")
        .load()
    )
