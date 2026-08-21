"""The telemetry schema, built from the shared contract.

Spark needs a fixed schema to read JSON from Kafka; inferring one from a stream
is not possible. That fixed schema is the thing that silently breaks when the
producer renames a field: Spark reads null for the missing column, every rule
depending on it stops matching, and no job fails and nothing is logged.

Building it from `contracts/telemetry-v1.json` rather than restating it here
means the two services cannot disagree about the payload without the contract
file itself changing, which is reviewable.
"""

import json
from functools import lru_cache

from pyspark.sql.types import DoubleType, StringType, StructField, StructType

from config import get_settings

# The contract is written in JSON Schema, whose type vocabulary is deliberately
# small. Numbers are read as doubles throughout: fill levels and temperatures
# are fractional, and reading an integral capacity as a double costs nothing.
JSON_TYPE_TO_SPARK = {
    "string": StringType(),
    "number": DoubleType(),
}

# The event-time column, and the field the contract marks as a timestamp. It
# arrives as an ISO 8601 string and is cast once, in the cleaning step.
EVENT_TIME_FIELD = "timestamp"
EVENT_TIME_COLUMN = "event_time"


@lru_cache
def load_contract() -> dict:
    """Read and parse the shared telemetry contract."""
    return json.loads(get_settings().CONTRACT_PATH.read_text())


@lru_cache
def telemetry_schema() -> StructType:
    """The Spark schema for a telemetry message body.

    Every field is nullable, which is deliberate: a message missing a field
    should reach the validation step and be dead-lettered with a reason, rather
    than failing to parse and being discarded with no explanation.
    """
    contract = load_contract()

    return StructType(
        [
            StructField(name, JSON_TYPE_TO_SPARK[spec["type"]], nullable=True)
            for name, spec in contract["properties"].items()
        ]
    )


@lru_cache
def range_rules() -> tuple[tuple[str, float | None, float | None], ...]:
    """The numeric bounds the contract declares, as (field, minimum, maximum).

    Used to build the validation step, so the ranges a reading is checked
    against are the published ones rather than a second set that can drift from
    them.
    """
    rules = []

    for name, spec in load_contract()["properties"].items():
        if spec["type"] != "number":
            continue

        minimum = spec.get("minimum", spec.get("exclusiveMinimum"))
        maximum = spec.get("maximum")

        if minimum is None and maximum is None:
            continue

        rules.append((name, minimum, maximum))

    return tuple(rules)


@lru_cache
def required_fields() -> tuple[str, ...]:
    """Fields a message must carry to be usable."""
    return tuple(load_contract()["required"])
