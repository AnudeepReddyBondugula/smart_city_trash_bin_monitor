"""Tests for the schema built from the shared telemetry contract.

The failure these guard against is silent. Spark reads Kafka JSON against a
fixed schema, so a field the schema does not know about is simply absent: every
rule reading it sees null, stops matching, and nothing fails or logs. Building
the schema from the contract is what makes that impossible without an explicit,
reviewable change to the contract file.
"""

from pyspark.sql.types import DoubleType, StringType

from schema import (
    EVENT_TIME_FIELD,
    load_contract,
    range_rules,
    required_fields,
    telemetry_schema,
)


def test_schema_covers_every_contracted_field():
    """No contracted field is missing from the schema Spark reads with."""
    assert set(telemetry_schema().fieldNames()) == set(load_contract()["properties"])


def test_schema_types_follow_the_contract():
    """Numbers are read as doubles and text as strings."""
    fields = {field.name: field.dataType for field in telemetry_schema().fields}

    assert fields["bin_id"] == StringType()
    assert fields["zone"] == StringType()
    assert fields[EVENT_TIME_FIELD] == StringType()
    assert fields["capacity"] == DoubleType()
    assert fields["current_fill_level"] == DoubleType()
    assert fields["temperature"] == DoubleType()


def test_every_field_is_nullable():
    """A missing field must reach validation, not fail to parse.

    Failing to parse discards the message with no explanation; reaching
    validation dead-letters it with a reason someone can act on.
    """
    assert all(field.nullable for field in telemetry_schema().fields)


def test_range_rules_cover_the_fields_with_bounds():
    """The bounds used for validation come from the contract."""
    rules = dict((name, (low, high)) for name, low, high, _ in range_rules())

    assert rules["battery_level"] == (0, 100)
    assert rules["latitude"] == (-90, 90)
    assert rules["temperature"][1] == 120


def test_temperature_range_admits_a_fire_risk_reading():
    """Validation must not reject the readings fire detection exists to catch.

    An ambient-only range would dead-letter every bin above 70 C, which is
    precisely the condition the fire rule looks for - and the rule would then
    never fire, with the readings discarded as impossible upstream.
    """
    rules = dict((name, (low, high)) for name, low, high, _ in range_rules())

    assert rules["temperature"][1] > 70


def test_required_fields_match_the_contract():
    """Every property is required; the contract does not carry optional fields."""
    assert set(required_fields()) == set(load_contract()["properties"])


def test_the_batch_job_does_not_take_the_streaming_ui_port():
    """The two applications run together and need separate UI ports.

    Sharing one means the batch job is pushed onto whatever Spark finds free,
    so the address changes run to run and the log carries a warning that reads
    like a fault.
    """
    from config import get_settings

    settings = get_settings()

    assert settings.SPARK_UI_PORT != settings.SPARK_BATCH_UI_PORT


def test_the_capacity_minimum_is_exclusive():
    """`exclusiveMinimum: 0` means more than zero, not at least zero.

    Flattened to an inclusive bound, a zero-capacity message is accepted and
    divides to a null fill percentage, which the stateful operator then
    compares against a threshold and dies on.
    """
    rules = {name: exclusive for name, _, _, exclusive in range_rules()}

    assert rules["capacity"] is True
    assert rules["current_fill_level"] is False


def test_the_contract_names_the_fields_that_cannot_be_empty():
    from schema import non_empty_fields

    assert set(non_empty_fields()) == {"bin_id", "zone"}


def test_the_dashboard_views_are_built_with_the_pipeline_thresholds():
    """The views and the alert rules must not disagree about "critical".

    Hardcoded in the SQL, the demo profile's one-minute offline threshold left
    city_kpi calling a bin active for fourteen minutes after it was alerted
    offline.
    """
    from config import get_settings
    from sinks import schema_sql

    settings = get_settings()
    sql = schema_sql()

    assert "{" not in sql, "a placeholder was left unfilled"
    assert f"{settings.CRITICAL_FILL_PCT}" in sql
    assert f"{settings.OFFLINE_AFTER_MINUTES} * INTERVAL '1 minute'" in sql
    assert "SLA_BREACH%" in sql
