"""Query 3 - five-minute aggregates per zone.

Five of the client's questions are the same numbers at different grains: daily
collection efficiency, which zone generates the most waste, peak hours, the
dashboard headline figures and long-range trends. Rather than a query each, this
writes one five-minute aggregate per zone and lets SQL roll it up to hourly,
daily, weekly or monthly.

That keeps a month of history out of streaming state, which streaming holds
badly, and it means the dashboard costs no Spark code at all - it is a view.

Twelve windows an hour across a handful of zones is a couple of thousand rows a
day, which PostgreSQL does not notice.
"""

import logging

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    approx_count_distinct,
    avg,
    col,
    count,
    max as spark_max,
    sum as spark_sum,
    when,
    window,
)

from config import get_settings
from schema import EVENT_TIME_COLUMN
from sinks import write_batch

logger = logging.getLogger(__name__)
settings = get_settings()

WINDOW_DURATION = "5 minutes"

TABLE = "zone_metrics_5m"
KEY = ["window_start", "zone"]
COLUMNS = [
    "window_start",
    "window_end",
    "zone",
    "bins_reporting",
    "reading_count",
    "avg_fill_pct",
    "max_fill_pct",
    "avg_temperature",
    "max_temperature",
    "critical_readings",
    "overflow_readings",
]


def aggregate(clean_events: DataFrame) -> DataFrame:
    """
    Roll clean readings up into one row per zone per five-minute window.

    The counts of readings crossing each threshold are carried alongside the
    averages because an average hides the thing operations care about: a zone
    averaging 45% while a handful of its bins sit above 95% is not a calm zone.
    """
    return (
        clean_events.groupBy(
            window(col(EVENT_TIME_COLUMN), WINDOW_DURATION),
            col("zone"),
        )
        .agg(
            # Approximate because exact distinct counting holds every key seen
            # in the window, and the number only ever feeds a dashboard tile.
            approx_count_distinct("bin_id").alias("bins_reporting"),
            count("*").alias("reading_count"),
            avg("fill_pct").alias("avg_fill_pct"),
            spark_max("fill_pct").alias("max_fill_pct"),
            avg("temperature").alias("avg_temperature"),
            spark_max("temperature").alias("max_temperature"),
            spark_sum(
                when(col("fill_pct") >= settings.CRITICAL_FILL_PCT, 1).otherwise(0)
            ).alias("critical_readings"),
            spark_sum(
                when(col("fill_pct") >= settings.OVERFLOW_FILL_PCT, 1).otherwise(0)
            ).alias("overflow_readings"),
        )
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("zone"),
            *[
                col(name)
                for name in COLUMNS
                if name not in ("window_start", "window_end", "zone")
            ],
        )
    )


def _write(batch: DataFrame, batch_id: int) -> None:
    """Write one micro-batch of completed windows.

    Upserted rather than appended. Append mode emits each window once, but a
    failed write is retried with the same batch, and an append would then count
    that window twice.
    """
    write_batch(batch, TABLE, COLUMNS, KEY, mode="upsert")


def start(clean_events: DataFrame):
    """
    Start the zone aggregate query.

    Append output mode, so a window is written only once the watermark has moved
    past it and it can no longer change. That makes each row final on arrival,
    which is what lets the API read this table without worrying about revisions.
    """
    return (
        aggregate(clean_events)
        .writeStream.outputMode("append")
        .foreachBatch(_write)
        .option("checkpointLocation", settings.checkpoint_for("zone_metrics"))
        .trigger(processingTime=settings.TRIGGER_INTERVAL)
        .queryName("zone_metrics")
        .start()
    )
