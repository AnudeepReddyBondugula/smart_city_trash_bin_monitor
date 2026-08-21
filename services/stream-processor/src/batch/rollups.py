"""The nightly job - peak hours and longer-range trends.

Two of the client's questions ask when waste is generated fastest and how it
changes across weeks and seasons. Neither is a real-time question, and neither
should cost streaming state: holding a month of history in a streaming query is
something Spark does badly, and there is no reason to, because the history is
already on disk.

So this is a plain batch job over the Parquet the cleaning query writes. It runs
once a night against data that is already there, which means it cannot block
anything and cannot lose anything by failing - the next run recomputes the same
answer from the same files.

Collections are derived from the history here rather than read back from the
alerts table. The rate of change between consecutive readings is already being
computed for the fill rate, and a collection is a large negative one, so the
number costs nothing extra and the job needs no read path into PostgreSQL.
"""

import logging
import sys

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql.functions import (
    avg,
    col,
    count,
    countDistinct,
    hour,
    lag,
    lit,
    max as spark_max,
    sum as spark_sum,
    to_date,
    when,
)

from config import get_settings
from logging_config import setup_logging
from schema import EVENT_TIME_COLUMN
from session import build_session
from sinks import write_batch

logger = logging.getLogger(__name__)
settings = get_settings()

SECONDS_PER_HOUR = 3600.0

HOURLY_TABLE = "zone_hourly_profile"
HOURLY_COLUMNS = [
    "zone",
    "hour_of_day",
    "avg_fill_rate_pct_hour",
    "avg_fill_pct",
    "reading_count",
]

DAILY_TABLE = "zone_daily_trend"
DAILY_COLUMNS = [
    "zone",
    "day",
    "avg_fill_pct",
    "max_fill_pct",
    "avg_temperature",
    "avg_fill_rate_pct_hour",
    "bins_reporting",
    "collections",
]


def load_history(session: SparkSession) -> DataFrame:
    """Read the clean event history written by the streaming pipeline."""
    return session.read.parquet(settings.PARQUET_PATH)


def with_fill_rate(events: DataFrame) -> DataFrame:
    """
    Attach the rate of change between each reading and the one before it.

    A window function over the history, partitioned by bin so one bin's readings
    are never compared against another's, and ordered by event time so
    "previous" means what it says.

    Two derived columns come out of the same comparison: how fast the bin was
    filling, and whether it was emptied. Rates are expressed per hour rather than
    per reading so the number does not change meaning when the reporting
    interval is retuned.
    """
    previous = Window.partitionBy("bin_id").orderBy(EVENT_TIME_COLUMN)

    with_previous = events.withColumn(
        "prev_fill_pct", lag("fill_pct").over(previous)
    ).withColumn("prev_event_time", lag(EVENT_TIME_COLUMN).over(previous))

    elapsed_hours = (
        col(EVENT_TIME_COLUMN).cast("double") - col("prev_event_time").cast("double")
    ) / SECONDS_PER_HOUR

    return (
        with_previous.withColumn("elapsed_hours", elapsed_hours)
        .withColumn(
            "fill_rate_pct_hour",
            # Only rises count towards a fill rate. A drop is the bin being
            # emptied, and averaging that in would report zones as filling more
            # slowly the more often they are collected - backwards.
            when(
                (col("elapsed_hours") > 0)
                & (col("fill_pct") > col("prev_fill_pct")),
                (col("fill_pct") - col("prev_fill_pct")) / col("elapsed_hours"),
            ),
        )
        .withColumn(
            "collected",
            when(
                (col("prev_fill_pct") >= settings.COLLECTION_DROP_FROM_PCT)
                & (col("fill_pct") < settings.COLLECTION_DROP_TO_PCT),
                lit(1),
            ).otherwise(lit(0)),
        )
    )


def hourly_profile(rated: DataFrame) -> DataFrame:
    """
    When each zone generates waste fastest, by hour of day.

    Averaged across every day in the history, so this describes the shape of a
    typical day rather than any particular one.
    """
    return (
        rated.groupBy("zone", hour(col(EVENT_TIME_COLUMN)).alias("hour_of_day"))
        .agg(
            avg("fill_rate_pct_hour").alias("avg_fill_rate_pct_hour"),
            avg("fill_pct").alias("avg_fill_pct"),
            count("*").alias("reading_count"),
        )
        .select(*HOURLY_COLUMNS)
    )


def daily_trend(rated: DataFrame) -> DataFrame:
    """One row per zone per day, for week-over-week and seasonal comparison."""
    return (
        rated.groupBy("zone", to_date(col(EVENT_TIME_COLUMN)).alias("day"))
        .agg(
            avg("fill_pct").alias("avg_fill_pct"),
            spark_max("fill_pct").alias("max_fill_pct"),
            avg("temperature").alias("avg_temperature"),
            avg("fill_rate_pct_hour").alias("avg_fill_rate_pct_hour"),
            countDistinct("bin_id").alias("bins_reporting"),
            spark_sum("collected").alias("collections"),
        )
        .select(*DAILY_COLUMNS)
    )


def main() -> None:
    setup_logging()
    logger.info("Starting nightly rollups over %s", settings.PARQUET_PATH)

    # Its own UI port: this runs alongside the streaming application, which
    # already holds the default one.
    session = build_session(ui_port=settings.SPARK_BATCH_UI_PORT)

    try:
        history = load_history(session)
    except Exception:
        # Nothing has been written yet. Not a failure worth waking anyone for -
        # the next run picks it up once the streaming pipeline has produced
        # something to roll up.
        logger.warning(
            "No history at %s yet; nothing to roll up", settings.PARQUET_PATH
        )
        session.stop()
        return

    # Read once and reused by both rollups; without this the whole history is
    # scanned and the window function recomputed for each.
    rated = with_fill_rate(history).persist()

    try:
        hourly = hourly_profile(rated)
        write_batch(hourly, HOURLY_TABLE, HOURLY_COLUMNS, ["zone", "hour_of_day"], "upsert")
        logger.info("Wrote %s", HOURLY_TABLE)

        daily = daily_trend(rated)
        write_batch(daily, DAILY_TABLE, DAILY_COLUMNS, ["zone", "day"], "upsert")
        logger.info("Wrote %s", DAILY_TABLE)
    finally:
        rated.unpersist()
        session.stop()

    logger.info("Nightly rollups complete")


if __name__ == "__main__":
    sys.exit(main())
