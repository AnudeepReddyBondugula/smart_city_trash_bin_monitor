"""Tests that need a real stream rather than a batch DataFrame.

Almost everything in the pipeline is a plain DataFrame transformation and is
tested on batch data, which is faster and clearer. Two things are not:
deduplication needs a watermark, which only exists on a streaming DataFrame, and
the windowed aggregate only emits once a watermark has advanced past a window.

These run against a file source rather than Kafka so the tests need no broker.
The transformation under test is the same code the Kafka source drives.
"""

import json

import pytest
from pyspark.sql.functions import col, lit

from pipeline.clean import clean_events
from pipeline.zone_metrics import aggregate


def as_kafka_shape(stream):
    """Give a text stream the column shape the Kafka source produces."""
    return stream.select(
        col("value").cast("binary").alias("value"),
        lit("smartbin-telemetry-v1").alias("topic"),
        lit(0).alias("partition"),
        lit(0).cast("long").alias("offset"),
    )


@pytest.fixture
def run_stream(spark, tmp_path):
    """Write messages to a file source, run a transformation, return the rows.

    `processAllAvailable` blocks until every file has been consumed, so the
    assertions see a finished result rather than racing the query.
    """

    def run(transform, messages, table):
        source = tmp_path / "input"
        source.mkdir()
        (source / "events.json").write_text(
            "\n".join(json.dumps(message) for message in messages)
        )

        stream = spark.readStream.format("text").load(str(source))
        query = (
            transform(as_kafka_shape(stream))
            .writeStream.format("memory")
            .queryName(table)
            .outputMode("append")
            .option("checkpointLocation", str(tmp_path / f"checkpoint-{table}"))
            .start()
        )
        try:
            query.processAllAvailable()
        finally:
            query.stop()

        return spark.sql(f"SELECT * FROM {table}").collect()

    return run


def test_duplicate_events_are_removed(run_stream, telemetry):
    """The same reading sent twice is counted once.

    Deduplication keys on the bin and the event time, which is why a re-sent
    duplicate has to carry its original timestamp. This is the positive case for
    that: two byte-identical messages collapse to one.
    """
    event = telemetry()

    rows = run_stream(clean_events, [event, event, event], "dedupe_same")

    assert len(rows) == 1


def test_distinct_readings_are_all_kept(run_stream, telemetry):
    """Deduplication does not swallow genuine consecutive readings.

    The counterpart to the test above - a rule that dropped everything would
    pass that one and be badly wrong.
    """
    rows = run_stream(
        clean_events,
        [
            telemetry(timestamp="2026-08-22T10:00:00+00:00"),
            telemetry(timestamp="2026-08-22T10:00:05+00:00"),
            telemetry(timestamp="2026-08-22T10:00:10+00:00"),
        ],
        "dedupe_distinct",
    )

    assert len(rows) == 3


def test_the_same_instant_from_different_bins_is_not_a_duplicate(
    run_stream, telemetry
):
    """Two bins reporting at the same moment are two readings, not one."""
    rows = run_stream(
        clean_events,
        [telemetry(bin_id="BIN-A"), telemetry(bin_id="BIN-B")],
        "dedupe_bins",
    )

    assert len(rows) == 2


def test_fill_pct_is_attached_to_the_clean_stream(run_stream, telemetry):
    """The clean stream carries the percentage every downstream rule compares."""
    rows = run_stream(
        clean_events,
        [telemetry(capacity=240.0, current_fill_level=120.0)],
        "clean_fill_pct",
    )

    assert rows[0]["fill_pct"] == pytest.approx(50.0)


def test_unusable_messages_never_reach_the_clean_stream(run_stream, telemetry):
    """A message with nothing salvageable is filtered before anything sees it."""
    rows = run_stream(
        clean_events,
        [
            telemetry(bin_id="BIN-OK"),
            telemetry(bin_id="BIN-BAD", current_fill_level=9999.0),
        ],
        "clean_filters",
    )

    assert [row["bin_id"] for row in rows] == ["BIN-OK"]


def test_a_bin_with_one_broken_sensor_still_reaches_the_clean_stream(
    run_stream, telemetry
):
    """It stays in the stream, with only the unusable reading nulled.

    This is what keeps the bin in the state store, so it still goes on the
    collection list and still arms an offline timeout. Discarding the whole
    message made a bin that was publishing every few seconds invisible to
    every downstream figure.
    """
    rows = run_stream(
        clean_events,
        [telemetry(bin_id="BIN-HOT-SENSOR", temperature=999.0, current_fill_level=88.0)],
        "clean_repairs",
    )

    assert len(rows) == 1
    assert rows[0]["temperature"] is None
    assert rows[0]["fill_pct"] == pytest.approx(88.0)
    assert "temperature" in rows[0]["sensor_faults"]


def test_the_stateful_operator_runs_under_spark(run_stream, telemetry):
    """The per-bin rules are exercised through the real Spark operator.

    The rules themselves are tested directly and far more thoroughly without a
    cluster. What this covers is the wiring those tests cannot: that the state
    schema round-trips through Spark's state store, that the pandas frames the
    operator yields match the declared output schema, and that grouping by bin
    reaches the function at all.
    """
    from pipeline.bin_state import RECORD_ALERT, RECORD_STATE, evaluate

    def transform(raw):
        return evaluate(clean_events(raw))

    messages = [
        telemetry(
            bin_id="BIN-FILLING",
            timestamp=f"2026-08-22T10:{index:02d}:00+00:00",
            # Crosses the critical threshold partway through
            current_fill_level=40.0 + index * 5,
        )
        for index in range(12)
    ]

    rows = run_stream(transform, messages, "stateful")

    by_type = {row["record_type"] for row in rows}
    assert RECORD_STATE in by_type
    assert RECORD_ALERT in by_type

    alerts = {row["alert_type"] for row in rows if row["record_type"] == RECORD_ALERT}
    assert "CRITICAL_FILL" in alerts

    state_rows = [row for row in rows if row["record_type"] == RECORD_STATE]
    assert state_rows[-1]["bin_id"] == "BIN-FILLING"
    assert state_rows[-1]["last_seen"] is not None


def test_zone_windows_aggregate_readings(run_stream, telemetry):
    """A five-minute window carries the counts and averages rollups need.

    Append mode only emits a window once the watermark has moved past it, so the
    input spans well over the window and watermark to force one closed.
    """

    def transform(raw):
        return aggregate(clean_events(raw))

    messages = [
        telemetry(
            bin_id=f"BIN-{index % 3}",
            timestamp=f"2026-08-22T10:{index:02d}:00+00:00",
            current_fill_level=90.0 if index % 3 == 0 else 20.0,
        )
        for index in range(45)
    ]

    rows = run_stream(transform, messages, "zone_windows")

    assert rows, "no window was emitted"

    first = rows[0]
    assert first["zone"] == "CENTRAL"
    assert first["bins_reporting"] == 3
    assert first["reading_count"] > 0
    # One bin in three is at 90%, which is over the critical threshold
    assert first["critical_readings"] > 0
    assert first["max_fill_pct"] == pytest.approx(90.0)
