"""Stream processor entrypoint.

Reads the telemetry topic once and starts the streaming queries on it. Each
query keeps its own checkpoint, so one failing does not stop the others and any
one of them can be reset without disturbing the rest.
"""

import logging
import signal
import threading

from config import get_settings
from logging_config import setup_logging
from pipeline import bin_state, clean, zone_metrics
from session import build_session, read_telemetry
from sinks import apply_schema

setup_logging()

logger = logging.getLogger(__name__)
settings = get_settings()

# How long to block in the JVM before returning to Python to notice a signal.
# Python runs a signal handler between bytecodes, so while the main thread sits
# inside a py4j call nothing is noticed - which is why an unbounded wait here
# meant SIGTERM was ignored until Docker gave up and sent SIGKILL.
SHUTDOWN_POLL_SECONDS = 5


def start_parquet_history(clean_events):
    """
    Write every clean reading to Parquet, partitioned by date.

    This is the history the batch job reads, and the only place a question
    nobody has asked yet can still be answered from.
    """
    return (
        clean.partitioned_by_date(clean_events)
        .writeStream.format("parquet")
        .outputMode("append")
        .partitionBy("event_date")
        .option("path", settings.PARQUET_PATH)
        .option("checkpointLocation", settings.checkpoint_for("bin_events"))
        .trigger(processingTime=settings.TRIGGER_INTERVAL)
        .queryName("bin_events")
        .start()
    )


def start_dead_letters(raw):
    """
    Forward messages that could not be believed to the dead-letter topic.

    Kept as its own query rather than folded into the history write, so a
    problem publishing dead letters cannot stop clean data being stored.
    """
    return (
        clean.dead_letters(raw)
        .writeStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.KAFKA_BOOTSTRAP_SERVERS)
        .option("topic", settings.KAFKA_DLQ_TOPIC)
        .option("checkpointLocation", settings.checkpoint_for("dead_letters"))
        .trigger(processingTime=settings.TRIGGER_INTERVAL)
        .queryName("dead_letters")
        .start()
    )


def run(session, queries, stop_requested: threading.Event) -> None:
    """
    Block until a query ends or a stop is asked for, then shut down in order.

    Stopping the queries rather than letting the process be killed lets each one
    finish the micro-batch it is in and commit its offsets. Nothing is lost
    either way - checkpoints exist for exactly that, and every write is
    idempotent - but a killed container reports as a crash, which is a bad
    signal to leave in `docker compose ps` for an ordinary stop.
    """
    while not stop_requested.is_set():
        # Raises if a query failed, which is how a failure still surfaces.
        if session.streams.awaitAnyTermination(timeout=SHUTDOWN_POLL_SECONDS):
            logger.warning("A streaming query ended on its own")
            break

    for query in queries:
        if query.isActive:
            logger.info("Stopping query %s", query.name)
            query.stop()

    session.stop()
    logger.info("Shutdown complete")


def main() -> None:
    logger.info("Starting stream processor")

    apply_schema()

    session = build_session()
    raw = read_telemetry(session)
    clean_events = clean.clean_events(raw)

    queries = [
        start_parquet_history(clean_events),
        start_dead_letters(raw),
        zone_metrics.start(clean_events),
        bin_state.start(clean_events),
    ]

    logger.info(
        "Started %d streaming quer(ies): %s",
        len(queries),
        ", ".join(query.name for query in queries),
    )

    stop_requested = threading.Event()

    def handle_shutdown(*_):
        logger.info("Shutdown signal received")
        stop_requested.set()

    for received in (signal.SIGINT, signal.SIGTERM):
        signal.signal(received, handle_shutdown)

    run(session, queries, stop_requested)


if __name__ == "__main__":
    main()
