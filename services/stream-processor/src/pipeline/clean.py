"""Query 1 - parse, validate, deduplicate.

This is the shared front of the pipeline: every other query reads its output, so
a reading is parsed, checked and deduplicated exactly once no matter how many
consumers it has. It is a plain DataFrame transformation rather than a hop
through storage, so nothing is written and read back between queries.

Two of the client's problems are answered here outright. Duplicate events are
removed, and readings no sensor could have produced are separated out - the
other half of that problem, a fill level that jumps impossibly between two
readings, needs the previous reading and belongs to the stateful query.
"""

import logging

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    coalesce,
    col,
    concat_ws,
    from_json,
    lit,
    struct,
    to_date,
    to_json,
    to_timestamp,
    when,
)

from config import get_settings
from schema import (
    EVENT_TIME_COLUMN,
    EVENT_TIME_FIELD,
    range_rules,
    required_fields,
    telemetry_schema,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Columns carried through to every downstream query.
CLEAN_COLUMNS = [
    "bin_id",
    "zone",
    "capacity",
    "current_fill_level",
    "fill_pct",
    "battery_level",
    "temperature",
    "latitude",
    "longitude",
    EVENT_TIME_COLUMN,
]


def parse(raw: DataFrame) -> DataFrame:
    """
    Turn Kafka records into typed telemetry columns.

    The raw value is kept alongside the parsed columns so a message that fails
    validation can be dead-lettered exactly as it arrived, rather than as a
    partial reconstruction of itself.
    """
    return (
        raw.select(
            col("value").cast("string").alias("raw_value"),
            col("topic"),
            col("partition"),
            col("offset"),
            from_json(col("value").cast("string"), telemetry_schema()).alias("data"),
        )
        .select("raw_value", "topic", "partition", "offset", "data.*")
        .withColumn(
            EVENT_TIME_COLUMN,
            to_timestamp(col(EVENT_TIME_FIELD)),
        )
    )


def rejection_reason(parsed: DataFrame):
    """
    Build the column naming why a reading is not believable, or null if it is.

    The range checks come from the shared contract rather than being restated
    here, so the bounds a reading is judged against are the published ones. This
    matters in both directions: too narrow a range rejects the very readings a
    rule exists to catch - a bin above 70 C is exactly what fire risk detection
    is looking for, and would be discarded as impossible by an ambient-only
    range.

    A reading gets every reason that applies rather than just the first, since
    knowing a message failed three checks is more useful than knowing it failed
    one.
    """
    reasons = []

    # A message that did not parse at all arrives as a row of nulls.
    reasons.append(
        when(col("bin_id").isNull(), lit("unparseable_or_missing_bin_id"))
    )

    for field in required_fields():
        if field == "bin_id":
            continue
        reasons.append(when(col(field).isNull(), lit(f"missing_{field}")))

    reasons.append(
        when(col(EVENT_TIME_COLUMN).isNull(), lit("unparseable_timestamp"))
    )

    for field, minimum, maximum in range_rules():
        if minimum is not None:
            reasons.append(
                when(col(field) < lit(minimum), lit(f"{field}_below_{minimum}"))
            )
        if maximum is not None:
            reasons.append(
                when(col(field) > lit(maximum), lit(f"{field}_above_{maximum}"))
            )

    # A bin cannot hold more than it holds. This is a relationship between two
    # fields rather than a bound on one, so it has no place in the contract's
    # per-field ranges and is checked here.
    reasons.append(
        when(
            col("current_fill_level") > col("capacity"),
            lit("fill_level_exceeds_capacity"),
        )
    )

    # concat_ws drops nulls, so unmatched checks contribute nothing and a
    # believable reading produces an empty string, normalised to null below.
    joined = concat_ws(",", *reasons)
    return when(joined == "", lit(None).cast("string")).otherwise(joined)


def split_valid_and_rejected(parsed: DataFrame) -> tuple[DataFrame, DataFrame]:
    """
    Separate believable readings from the rest.

    Rejected messages are not dropped. A dropped message is indistinguishable
    from one that was never sent, which matters here more than usual: dead
    device detection works by noticing an absence, so silently discarding a
    bin's messages would make a healthy bin look dead.
    """
    flagged = parsed.withColumn("reject_reason", rejection_reason(parsed))

    valid = flagged.filter(col("reject_reason").isNull())
    rejected = flagged.filter(col("reject_reason").isNotNull())

    return valid, rejected


def clean_events(raw: DataFrame) -> DataFrame:
    """
    The clean stream every downstream query reads.

    Deduplication runs before anything else, so no duplicate ever reaches the
    stateful operator or the aggregates. It keys on (bin_id, event time) within
    the watermark, which is why a re-sent duplicate has to carry its original
    timestamp - a fresh one makes it a distinct event that passes straight
    through.

    Note there is no join here. Zone and capacity travel on every event, so the
    stream needs no lookup against the bins table at all. That removes a
    database dependency from the hot path, and with it the problem of a bin
    registered after the job started being enriched with nulls.
    """
    valid, _ = split_valid_and_rejected(parse(raw))

    return (
        valid.withWatermark(EVENT_TIME_COLUMN, settings.WATERMARK)
        .dropDuplicatesWithinWatermark(["bin_id", EVENT_TIME_COLUMN])
        .withColumn(
            "fill_pct",
            # Guarded rather than assumed: capacity is validated as positive
            # upstream, but a division that can produce infinity would poison
            # every average downstream, and one bad row is not worth that.
            when(
                col("capacity") > 0,
                col("current_fill_level") / col("capacity") * 100,
            ).otherwise(lit(None).cast("double")),
        )
        .select(*CLEAN_COLUMNS)
    )


def dead_letters(raw: DataFrame) -> DataFrame:
    """
    The rejected messages, shaped for the dead-letter topic.

    Keyed by bin_id where one could be read, so a bin's bad messages land on one
    partition alongside a record of where they came from.
    """
    _, rejected = split_valid_and_rejected(parse(raw))

    return rejected.select(
        coalesce(col("bin_id"), lit("unknown")).cast("string").alias("key"),
        # Built with Spark's own JSON writer so the original payload is embedded
        # as a properly escaped string. An unparseable message is exactly the
        # kind that contains whatever would break a hand-assembled envelope.
        to_json(
            struct(
                col("reject_reason").alias("reason"),
                col("topic").alias("source_topic"),
                col("partition").alias("source_partition"),
                col("offset").alias("source_offset"),
                col("raw_value").alias("payload"),
            )
        ).alias("value"),
    )


def partitioned_by_date(clean: DataFrame) -> DataFrame:
    """Add the date column the Parquet history is partitioned by."""
    return clean.withColumn("event_date", to_date(col(EVENT_TIME_COLUMN)))
