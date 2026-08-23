"""Assert the published payload matches the shared telemetry contract.

`contracts/telemetry-v1.json` at the repository root is the agreement between
this service and every consumer of `smartbin-telemetry-v1`. The consumer builds
a fixed schema from that file, which means a field renamed here and not there
does not raise anything: the consumer reads nulls for the renamed column, every
rule that depends on it silently stops matching, and no job fails. This test is
the half of that agreement the producer is responsible for.

The checks are deliberately name-and-type only, with no JSON Schema library. The
failure this guards against is a field disappearing or changing shape; the value
ranges in the contract are enforced by the consumer, which rejects out-of-range
readings to a dead-letter topic rather than trusting the producer.
"""

import json
from pathlib import Path

import pytest

from src.models.bin import Bin

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "telemetry-v1.json"
)

JSON_TYPE_CHECKS = {
    "string": str,
    "number": (int, float),
}


@pytest.fixture(scope="module")
def contract():
    """The parsed telemetry contract."""
    return json.loads(CONTRACT_PATH.read_text())


@pytest.fixture
def payload():
    """A payload from a bin carrying non-default values in every field."""
    bin_instance = Bin("bin_1", 240.0, 17.4, 78.5, "NORTH")
    bin_instance.current_fill_level = 123.456
    bin_instance.battery_level = 80.456
    bin_instance.temperature = 71.5
    return bin_instance.to_payload()


def test_contract_file_exists():
    """The shared contract is where both services expect to find it."""
    assert CONTRACT_PATH.is_file(), f"missing contract at {CONTRACT_PATH}"


def test_payload_fields_match_the_contract_exactly(contract, payload):
    """The payload has every contracted field and no field the contract omits."""
    assert set(payload) == set(contract["properties"])
    # required and properties must not drift apart within the contract itself
    assert set(contract["required"]) == set(contract["properties"])


def test_payload_field_types_match_the_contract(contract, payload):
    """Every payload value has the JSON type the contract declares."""
    for field, spec in contract["properties"].items():
        expected = JSON_TYPE_CHECKS[spec["type"]]
        assert isinstance(payload[field], expected), (
            f"{field} is {type(payload[field]).__name__}, "
            f"contract says {spec['type']}"
        )


def test_payload_values_sit_inside_the_contracted_ranges(contract, payload):
    """A routine payload is not itself rejected by the ranges we publish."""
    for field, spec in contract["properties"].items():
        value = payload[field]
        if "minimum" in spec:
            assert value >= spec["minimum"], f"{field}={value} below minimum"
        if "maximum" in spec:
            assert value <= spec["maximum"], f"{field}={value} above maximum"
        if "exclusiveMinimum" in spec:
            assert value > spec["exclusiveMinimum"], f"{field}={value} too low"


def test_contract_permits_a_hot_bin_but_not_an_impossible_one(contract):
    """The temperature range admits fire-risk readings and rejects sensor faults.

    Fire risk is detected above 70 C, so if the contract capped temperature at
    ambient the consumer would reject exactly the readings the rule exists to
    catch. The SPIKE fault must still fall outside.
    """
    from src.simulator.bin_simulator import IMPOSSIBLE_TEMPERATURE

    temperature = contract["properties"]["temperature"]

    assert temperature["maximum"] > 70
    assert IMPOSSIBLE_TEMPERATURE > temperature["maximum"]
