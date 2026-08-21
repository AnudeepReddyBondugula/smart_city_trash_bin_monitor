"""Stream processor entrypoint.

Reads the telemetry topic once and starts the streaming queries on it. Each
query keeps its own checkpoint, so one failing does not stop the others and any
one of them can be reset without disturbing the rest.
"""

import logging

from config import get_settings
from logging_config import setup_logging
from pipeline import bin_state, clean, zone_metrics
from session import build_session, read_telemetry
from sinks import apply_schema

setup_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


def start_parquet_history(clean_events):
    """
    Write every clean reading to Parquet, partitioned by date.

    This is the history the nightly job reads, and the only place a question
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

    # Blocks until any query fails, which surfaces the failure instead of
    # leaving the process alive with a dead query inside it.
    session.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
