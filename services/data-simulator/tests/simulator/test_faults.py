"""Tests for injected bin faults.

Each fault exists so that one downstream detector has something to detect. These
tests assert the fault actually produces the condition its detector looks for -
not merely that a flag was set - because a fault that never produces its
condition and a detector that never fires are indistinguishable in a demo.
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.config import get_settings
from src.models.bin import Bin
from src.simulator.bin_simulator import (
    FAULT_MODES,
    IMPOSSIBLE_TEMPERATURE,
    BinSimulator,
    assign_fault_modes,
)

settings = get_settings()

# The thresholds the consumer applies. Duplicated here on purpose: if either
# side moves, these tests should fail rather than quietly agree with themselves.
FIRE_RISK_TEMPERATURE = 70.0
FIRE_RISK_FILL_PCT = 80.0


def make_bin(fault_mode=None, capacity=100.0):
    return Bin("bin_1", capacity, 17.4, 78.5, "NORTH", fault_mode=fault_mode)


def tick(simulator, count=1):
    """Advance the simulation by whole ticks."""
    for _ in range(count):
        simulator._simulate()


# --------------------------------------------------------------------------
# Fault assignment
# --------------------------------------------------------------------------


def test_assign_fault_modes_covers_every_mode():
    """Enough faulty bins means every fault mode is represented.

    Drawing per bin independently can leave a small fleet with no HOT bin at
    all, so no fire-risk alert ever fires and the detector looks broken.
    """
    bins = [make_bin() for _ in range(len(FAULT_MODES) * 10)]

    assign_fault_modes(bins, rate=1.0)

    assert {bin_instance.fault_mode for bin_instance in bins} == set(FAULT_MODES)


def test_assign_fault_modes_leaves_most_bins_healthy():
    """Only the configured share of the fleet misbehaves."""
    bins = [make_bin() for _ in range(100)]

    assign_fault_modes(bins, rate=0.12)

    faulty = [b for b in bins if b.fault_mode is not None]
    assert len(faulty) == 12
    assert all(b.fault_mode is None for b in bins[12:])


def test_assign_fault_modes_can_be_disabled():
    """A rate of zero leaves every bin healthy."""
    bins = [make_bin() for _ in range(50)]

    assign_fault_modes(bins, rate=0.0)

    assert all(b.fault_mode is None for b in bins)


# --------------------------------------------------------------------------
# SILENT - dead device detection
# --------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.simulator.bin_simulator.kafka_client")
@patch("src.simulator.bin_simulator.asyncio.sleep")
async def test_silent_bin_publishes_nothing(mock_sleep, mock_kafka_client):
    """A silent bin stops sending, which is what dead-device detection sees."""
    mock_kafka_client.send_telemetry = AsyncMock()
    simulator = BinSimulator(make_bin("SILENT"))
    simulator._running = True

    async def stop(*args, **kwargs):
        simulator._running = False

    mock_sleep.side_effect = stop

    await simulator._run()

    mock_kafka_client.send_telemetry.assert_not_called()


# --------------------------------------------------------------------------
# FROZEN - stuck sensor detection
# --------------------------------------------------------------------------


def test_frozen_bin_never_changes_its_reading():
    """A frozen bin repeats one reading, which is a stuck sensor."""
    bin_instance = make_bin("FROZEN")
    bin_instance.current_fill_level = 42.0
    simulator = BinSimulator(bin_instance)

    tick(simulator, count=20)

    assert bin_instance.current_fill_level == 42.0


@pytest.mark.asyncio
@patch("src.simulator.bin_simulator.kafka_client")
@patch("src.simulator.bin_simulator.asyncio.sleep")
async def test_frozen_bin_still_publishes(mock_sleep, mock_kafka_client):
    """A frozen bin keeps reporting - it is stuck, not offline.

    This is what separates it from a SILENT bin: the events keep arriving, so
    the fault has to be found by noticing the value never moves.
    """
    mock_kafka_client.send_telemetry = AsyncMock()
    simulator = BinSimulator(make_bin("FROZEN"))
    simulator._running = True

    async def stop(*args, **kwargs):
        simulator._running = False

    mock_sleep.side_effect = stop

    await simulator._run()

    mock_kafka_client.send_telemetry.assert_called_once()


# --------------------------------------------------------------------------
# SPIKE - impossible values, rejected to the dead-letter topic
# --------------------------------------------------------------------------


def test_spike_bin_reports_an_impossible_temperature():
    """A spiking bin reports a value no sensor could produce."""
    bin_instance = make_bin("SPIKE")
    simulator = BinSimulator(bin_instance)

    tick(simulator)

    assert bin_instance.temperature == IMPOSSIBLE_TEMPERATURE


# --------------------------------------------------------------------------
# DUPLICATE - deduplication
# --------------------------------------------------------------------------


def test_duplicate_bin_resends_the_previous_event_unchanged():
    """A duplicate carries the original timestamp, so it is really a duplicate.

    Deduplication keys on (bin_id, timestamp). Regenerating the timestamp would
    produce a distinct event that passes straight through, leaving the rule with
    nothing to remove.
    """
    simulator = BinSimulator(make_bin("DUPLICATE"))

    first = simulator._next_payload()
    second = simulator._next_payload()

    assert second == first
    assert second["timestamp"] == first["timestamp"]


def test_duplicate_bin_alternates_so_it_still_makes_progress():
    """After re-sending, the bin emits a fresh reading rather than stalling."""
    simulator = BinSimulator(make_bin("DUPLICATE"))

    first = simulator._next_payload()
    simulator._next_payload()  # the duplicate
    third = simulator._next_payload()

    assert third["timestamp"] != first["timestamp"]


def test_healthy_bin_never_repeats_an_event():
    """Deduplication must not have anything to do on a healthy bin."""
    simulator = BinSimulator(make_bin())

    timestamps = {simulator._next_payload()["timestamp"] for _ in range(5)}

    assert len(timestamps) == 5


# --------------------------------------------------------------------------
# HOT - fire risk detection
# --------------------------------------------------------------------------


@pytest.mark.parametrize("capacity", [100.0, 240.0, 660.0])
def test_hot_bin_is_hot_and_full_at_the_same_time(capacity):
    """A hot bin satisfies both halves of the fire-risk rule together.

    Fire risk means temperature above 70 C *and* fill above 80%. A bin that
    pinned itself to a high temperature while empty would satisfy one half
    forever and the other never, and the alert would still not fire. Scaling the
    temperature with fill level holds at every bin size.
    """
    bin_instance = make_bin("HOT", capacity=capacity)
    simulator = BinSimulator(bin_instance)

    bin_instance.current_fill_level = capacity * 0.85
    simulator._simulate_temperature()

    assert bin_instance.fill_pct > FIRE_RISK_FILL_PCT
    assert bin_instance.temperature > FIRE_RISK_TEMPERATURE


def test_hot_bin_is_not_yet_alarming_while_half_empty():
    """A hot bin below the fill threshold does not raise a false fire alarm."""
    bin_instance = make_bin("HOT")
    simulator = BinSimulator(bin_instance)

    bin_instance.current_fill_level = 50.0
    simulator._simulate_temperature()

    assert bin_instance.temperature < FIRE_RISK_TEMPERATURE


def test_hot_bin_stays_within_the_contracted_range():
    """Even at capacity a hot bin reports a believable temperature.

    A HOT bin is extreme but valid data and must reach the detector; only a
    SPIKE bin should be rejected as impossible.
    """
    bin_instance = make_bin("HOT")
    simulator = BinSimulator(bin_instance)

    bin_instance.current_fill_level = bin_instance.capacity
    simulator._simulate_temperature()

    assert bin_instance.temperature == settings.TEMP_FIRE_MAX
    assert bin_instance.temperature < IMPOSSIBLE_TEMPERATURE


def test_healthy_bin_never_reaches_fire_risk_temperature():
    """A healthy bin stays in the ambient band no matter how full it gets."""
    bin_instance = make_bin()
    bin_instance.current_fill_level = 99.0
    simulator = BinSimulator(bin_instance)

    tick(simulator, count=200)

    assert settings.TEMP_NORMAL_MIN <= bin_instance.temperature
    assert bin_instance.temperature <= settings.TEMP_NORMAL_MAX


# --------------------------------------------------------------------------
# UNCOLLECTED - SLA breach detection
# --------------------------------------------------------------------------


def test_uncollected_bin_is_never_emptied():
    """A bin the truck never comes for stays full, and breaches its SLA.

    Every healthy bin is emptied well inside the two hours the SLA allows, so
    without this fault the breach rule could never be observed firing.
    """
    bin_instance = make_bin("UNCOLLECTED")
    bin_instance.current_fill_level = bin_instance.capacity
    simulator = BinSimulator(bin_instance)

    tick(simulator, count=500)

    assert bin_instance.current_fill_level == bin_instance.capacity


def test_healthy_bin_is_eventually_collected():
    """The comparison case: a healthy bin does get emptied.

    Guards the SLA test above against passing for the wrong reason - a change
    that stopped every bin being collected would otherwise look fine.
    """
    bin_instance = make_bin()
    bin_instance.current_fill_level = bin_instance.capacity
    simulator = BinSimulator(bin_instance)

    for _ in range(2000):
        tick(simulator)
        if bin_instance.current_fill_level == 0:
            return

    pytest.fail("a healthy bin was never collected")


# --------------------------------------------------------------------------
# JUMP - abnormal jump detection
# --------------------------------------------------------------------------


def test_jump_bin_moves_far_more_than_a_healthy_one():
    """A jumping bin gains a suspicious amount between two readings."""
    jumping = make_bin("JUMP")
    healthy = make_bin()

    BinSimulator(jumping)._simulate_fill()
    BinSimulator(healthy)._simulate_fill()

    assert jumping.current_fill_level > healthy.current_fill_level * 10


def test_jump_bin_stays_a_believable_level():
    """The jump is large but legal, so a range check alone will not catch it.

    This is the point of the fault: it has to be found by comparing against the
    previous reading, not by validating one event in isolation.
    """
    bin_instance = make_bin("JUMP")
    simulator = BinSimulator(bin_instance)

    tick(simulator, count=10)

    assert 0 <= bin_instance.current_fill_level <= bin_instance.capacity
