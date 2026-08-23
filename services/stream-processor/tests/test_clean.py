"""Tests for Query 1 - parsing, validation and the dead-letter path.

The transformations under test are plain DataFrame functions, so they behave
identically on the batch DataFrames used here and on the real stream. The one
exception is deduplication, which needs a watermark and therefore a streaming
DataFrame; it is covered separately at the end.
"""

import json

import pytest
from pyspark.sql.functions import col

from pipeline.clean import (
    CLEAN_COLUMNS,
    dead_letters,
    parse,
    partitioned_by_date,
    split_valid_and_rejected,
)


def valid_rows(kafka_records, *payloads):
    """The believable readings out of a set of messages."""
    valid, _ = split_valid_and_rejected(parse(kafka_records(*payloads)))
    return valid.collect()


def rejections(kafka_records, *payloads):
    """The reject reasons produced by a set of messages."""
    _, rejected = split_valid_and_rejected(parse(kafka_records(*payloads)))
    return [row["reject_reason"] for row in rejected.collect()]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_a_healthy_reading_is_parsed_and_kept(kafka_records, telemetry):
    """A well-formed message survives validation with its values intact."""
    rows = valid_rows(kafka_records, telemetry())

    assert len(rows) == 1
    assert rows[0]["bin_id"] == "BIN-TEST-01"
    assert rows[0]["zone"] == "CENTRAL"
    assert rows[0]["temperature"] == 25.0


def test_the_timestamp_becomes_a_real_event_time(kafka_records, telemetry):
    """The ISO string is cast to a timestamp, which windowing depends on."""
    rows = valid_rows(kafka_records, telemetry())

    assert rows[0]["event_time"] is not None
    assert rows[0]["event_time"].year == 2026


def test_zone_arrives_without_any_database_lookup(kafka_records, telemetry):
    """Zone travels on the event, so the stream needs no join to enrich it.

    This is what removes the bins table from the hot path, and with it the case
    where a bin registered after the job started is enriched with nulls.
    """
    rows = valid_rows(kafka_records, telemetry(zone="NORTH"))

    assert rows[0]["zone"] == "NORTH"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_unparseable_message_is_rejected_not_dropped(kafka_records):
    """Malformed JSON is dead-lettered with a reason rather than discarded.

    Discarding it silently would be indistinguishable from the bin never having
    sent anything - which is exactly what dead-device detection looks for.
    """
    reasons = rejections(kafka_records, "this is not json at all")

    assert len(reasons) == 1
    assert "unparseable_or_missing_bin_id" in reasons[0]


def test_impossible_temperature_does_not_discard_the_whole_reading(
    kafka_records, telemetry
):
    """One dead sensor must not make the entire bin disappear.

    Rejecting the whole message here was a monitoring blind spot: the bin never
    reached the state store, so it vanished from every dashboard figure and
    never armed an offline timeout either. A bin publishing every few seconds
    became completely invisible, and the loudest sensor failure produced the
    quietest outcome.
    """
    rows = valid_rows(kafka_records, telemetry(temperature=150.0))

    assert len(rows) == 1
    assert rows[0]["bin_id"] == "BIN-TEST-01"


def test_an_impossible_temperature_is_nulled_not_kept(kafka_records, telemetry):
    """The unusable reading itself is discarded, only the reading."""
    rows = valid_rows(kafka_records, telemetry(temperature=150.0))

    assert rows[0]["temperature"] is None


def test_an_impossible_temperature_is_not_clamped(kafka_records, telemetry):
    """Clamping would invent a plausible number no sensor reported.

    120 C would then be averaged into the zone temperature as though it were a
    real measurement. A null is honest that the reading is missing.
    """
    rows = valid_rows(kafka_records, telemetry(temperature=150.0))

    assert rows[0]["temperature"] != 120.0


def test_the_usable_readings_survive_a_broken_sensor(kafka_records, telemetry):
    """Fill level is untouched by a thermometer failing."""
    rows = valid_rows(
        kafka_records,
        telemetry(temperature=150.0, current_fill_level=87.0, battery_level=64.0),
    )

    assert rows[0]["current_fill_level"] == 87.0
    assert rows[0]["battery_level"] == 64.0


def test_the_broken_sensor_is_named(kafka_records, telemetry):
    """The repair is recorded, so it can be alerted on rather than silent."""
    rows = valid_rows(kafka_records, telemetry(temperature=150.0))

    assert "temperature" in rows[0]["sensor_faults"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("battery_level", 140.0),
        ("battery_level", -5.0),
        ("latitude", 200.0),
        ("longitude", -400.0),
    ],
)
def test_every_repairable_sensor_is_handled(kafka_records, telemetry, field, value):
    """Each sensor that can fail alone is nulled and named, in both directions."""
    rows = valid_rows(kafka_records, telemetry(**{field: value}))

    assert len(rows) == 1
    assert rows[0][field] is None
    assert field in rows[0]["sensor_faults"]


def test_a_healthy_reading_reports_no_sensor_faults(kafka_records, telemetry):
    """The negative case: nothing is flagged when nothing is wrong."""
    rows = valid_rows(kafka_records, telemetry())

    assert rows[0]["sensor_faults"] is None


def test_several_broken_sensors_are_all_named(kafka_records, telemetry):
    rows = valid_rows(
        kafka_records, telemetry(temperature=150.0, battery_level=-5.0)
    )

    assert "temperature" in rows[0]["sensor_faults"]
    assert "battery_level" in rows[0]["sensor_faults"]


def test_a_hot_bin_is_believed(kafka_records, telemetry):
    """A dangerous but physically possible temperature is kept.

    The counterpart to the test above: if validation rejected these, fire risk
    detection would never see the readings it exists to act on.
    """
    rows = valid_rows(kafka_records, telemetry(temperature=85.0))

    assert len(rows) == 1
    assert rows[0]["temperature"] == 85.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capacity", -1.0),
        ("current_fill_level", -1.0),
    ],
)
def test_out_of_range_tracking_fields_are_rejected(
    kafka_records, telemetry, field, value
):
    """A bound on a field the pipeline needs is fatal to the whole message."""
    reasons = rejections(kafka_records, telemetry(**{field: value}))

    assert any(f"{field}_out_of_range" in reason for reason in reasons)


def test_fill_level_above_capacity_is_rejected(kafka_records, telemetry):
    """A bin cannot hold more than it holds.

    A relationship between two fields rather than a bound on one, so it cannot
    be expressed in the contract's per-field ranges.
    """
    reasons = rejections(
        kafka_records, telemetry(capacity=100.0, current_fill_level=150.0)
    )

    assert any("fill_level_exceeds_capacity" in reason for reason in reasons)


def test_a_missing_tracking_field_is_named_in_the_reason(kafka_records, telemetry):
    """The reason says which field was absent."""
    payload = telemetry()
    del payload["zone"]

    reasons = rejections(kafka_records, payload)

    assert any("missing_zone" in reason for reason in reasons)


def test_a_missing_sensor_reading_does_not_reject_the_message(
    kafka_records, telemetry
):
    """An absent sensor is a fault to report, not a message to throw away."""
    payload = telemetry()
    del payload["temperature"]

    rows = valid_rows(kafka_records, payload)

    assert len(rows) == 1
    assert "temperature" in rows[0]["sensor_faults"]


def test_all_failing_checks_are_reported_together(kafka_records, telemetry):
    """A message gets every reason that applies, not just the first."""
    payload = telemetry(capacity=-1.0)
    del payload["zone"]

    reasons = rejections(kafka_records, payload)

    assert "missing_zone" in reasons[0]
    assert "capacity_out_of_range" in reasons[0]


def test_valid_and_rejected_partition_the_input(kafka_records, telemetry):
    """Every message ends up on exactly one side. Nothing is lost."""
    messages = [
        telemetry(bin_id="good-1"),
        telemetry(bin_id="repairable", temperature=999.0),
        telemetry(bin_id="fatal", current_fill_level=9999.0),
        "not json",
        telemetry(bin_id="good-2"),
    ]

    parsed = parse(kafka_records(*messages))
    valid, rejected = split_valid_and_rejected(parsed)

    # The repairable one stays on the valid side, nulled rather than discarded
    assert valid.count() == 3
    assert rejected.count() == 2


# ---------------------------------------------------------------------------
# Fill percentage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("capacity", "level", "expected"),
    [(100.0, 50.0, 50.0), (240.0, 60.0, 25.0), (660.0, 594.0, 90.0)],
)
def test_fill_pct_is_computed_from_capacity(
    spark, kafka_records, telemetry, capacity, level, expected
):
    """Fill percentage accounts for the size of the bin.

    Every threshold downstream is a percentage while the payload carries an
    absolute level, so a 660 litre bin at 594 litres has to read as 90% full and
    not as an impossible 594%.
    """
    from pipeline.clean import parse as parse_records

    parsed = parse_records(
        kafka_records(telemetry(capacity=capacity, current_fill_level=level))
    )
    valid, _ = split_valid_and_rejected(parsed)

    row = valid.withColumn(
        "fill_pct", col("current_fill_level") / col("capacity") * 100
    ).collect()[0]

    assert row["fill_pct"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Dead letters
# ---------------------------------------------------------------------------


def test_dead_letter_carries_the_reason_and_the_original(kafka_records, telemetry):
    """A dead letter is actionable: it says why, and includes what arrived."""
    rows = dead_letters(
        kafka_records(telemetry(current_fill_level=9999.0))
    ).collect()

    assert len(rows) == 1
    envelope = json.loads(rows[0]["value"])

    assert "fill_level_exceeds_capacity" in envelope["reason"]
    assert envelope["source_partition"] == 0
    assert json.loads(envelope["payload"])["bin_id"] == "BIN-TEST-01"


def test_dead_letter_envelope_survives_a_hostile_payload(kafka_records):
    """A payload full of quotes and backslashes does not break the envelope.

    Unparseable messages are exactly the ones likely to contain whatever would
    corrupt a hand-assembled JSON string, which is why the envelope is built
    with a real JSON writer.
    """
    hostile = '{"bin_id": "x\\", "note": "he said \\"hi\\"", '

    rows = dead_letters(kafka_records(hostile)).collect()

    envelope = json.loads(rows[0]["value"])
    assert envelope["payload"] == hostile


def test_dead_letter_is_keyed_by_bin_where_known(kafka_records, telemetry):
    """Keying by bin keeps one bin's bad messages together on one partition."""
    rows = dead_letters(
        kafka_records(telemetry(current_fill_level=9999.0))
    ).collect()

    assert rows[0]["key"] == "BIN-TEST-01"


def test_dead_letter_key_falls_back_when_the_bin_is_unknown(kafka_records):
    """A message too broken to name a bin still gets published."""
    rows = dead_letters(kafka_records("garbage")).collect()

    assert rows[0]["key"] == "unknown"


# ---------------------------------------------------------------------------
# Parquet layout
# ---------------------------------------------------------------------------


def test_history_is_partitioned_by_event_date(spark, kafka_records, telemetry):
    """The history carries the date column it is partitioned by.

    Partitioning by date is what lets the batch job read one day without
    scanning the whole history.
    """
    parsed = parse(kafka_records(telemetry()))
    valid, _ = split_valid_and_rejected(parsed)
    dated = partitioned_by_date(
        valid.withColumn("fill_pct", col("current_fill_level"))
    )

    assert "event_date" in dated.columns
    assert str(dated.collect()[0]["event_date"]) == "2026-08-22"


def test_clean_columns_are_what_downstream_queries_expect():
    """The published column list contains everything the rules need."""
    for needed in ("bin_id", "zone", "fill_pct", "temperature", "battery_level"):
        assert needed in CLEAN_COLUMNS


# ---------------------------------------------------------------------------
# Regressions found in review
# ---------------------------------------------------------------------------


def test_a_zero_capacity_reading_is_rejected(kafka_records, telemetry):
    """The contract says capacity is greater than zero, and it must be enforced.

    Accepted, it divides to a null fill percentage, and every fill rule in the
    stateful operator compares that null against a threshold - which raises in
    the Python worker and takes the whole streaming application down. One
    message was enough.
    """
    reasons = rejections(kafka_records, telemetry(capacity=0.0))

    assert "capacity_out_of_range" in reasons[0]


def test_a_positive_capacity_is_still_accepted(kafka_records, telemetry):
    """The exclusive bound must reject zero without rejecting small bins."""
    rows = valid_rows(kafka_records, telemetry(capacity=0.5, current_fill_level=0.25))

    assert len(rows) == 1
    assert rows[0]["capacity"] == 0.5


def test_an_empty_bin_id_is_rejected(kafka_records, telemetry):
    """Empty is not null, and it passed every null check.

    All such events then group under one empty key in the stateful operator, so
    unrelated bins share a single state entry.
    """
    reasons = rejections(kafka_records, telemetry(bin_id=""))

    assert "empty_bin_id" in reasons[0]


def test_a_whitespace_zone_is_rejected(kafka_records, telemetry):
    reasons = rejections(kafka_records, telemetry(zone="   "))

    assert "empty_zone" in reasons[0]


def test_no_valid_reading_can_divide_to_a_null_fill_percentage(kafka_records, telemetry):
    """The one guarantee the stateful operator relies on and cannot check.

    fill_pct is computed as a guarded division, so a capacity of zero would
    reach the operator as a null. Validation is what makes that unreachable.
    """
    rows = valid_rows(
        kafka_records, telemetry(), telemetry(capacity=240.0), telemetry(capacity=0.0)
    )

    assert all(row["capacity"] > 0 for row in rows)
