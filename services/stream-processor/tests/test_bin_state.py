"""Tests for Query 2 - the per-bin rules.

The rules are plain Python over a dictionary of remembered values, so they are
tested directly with no Spark session. That is deliberate: these ten rules carry
almost all the behaviour anyone will argue about, and they should be readable and
fast to check.

Every rule gets both a positive case and the case that must NOT fire. A rule that
fires on everything and a rule that fires correctly look identical if only the
positive case is tested.
"""

import pandas as pd
import pytest

from config import get_settings
from pipeline.bin_state import (
    EMPTY_STATE,
    OUTPUT_SCHEMA,
    RECORD_ALERT,
    RECORD_STATE,
    STATE_FIELDS,
    evaluate_reading,
    fill_projection,
    track_bin,
)

settings = get_settings()

BIN = "BIN-TEST-01"
START_MS = 1_755_000_000_000  # a fixed instant, so tests read deterministically


def reading(**overrides):
    """A healthy reading, with only what a test is about overridden."""
    values = {
        "zone": "CENTRAL",
        "capacity": 100.0,
        "current_fill_level": 50.0,
        "fill_pct": 50.0,
        "temperature": 25.0,
        "battery_level": 80.0,
        "latitude": 17.4,
        "longitude": 78.5,
        "event_ms": START_MS,
    }
    values.update(overrides)
    return values


def fresh_memory():
    return dict(EMPTY_STATE)


def feed(memory, *readings):
    """Apply readings in order, returning every alert type raised."""
    fired = []
    for values in readings:
        fired.extend(
            alert["alert_type"] for alert in evaluate_reading(memory, values, BIN)
        )
    return fired


def minutes(count):
    return int(count * 60_000)


class FakeGroupState:
    """A stand-in for Spark's GroupState.

    Small enough to be obviously correct, which is what makes it worth having:
    it lets the whole operator be driven without a cluster.
    """

    def __init__(self, values=None, timed_out=False, watermark_ms=0):
        self._values = values
        self.hasTimedOut = timed_out
        self._watermark_ms = watermark_ms
        self.timeout_timestamp = None

    @property
    def exists(self):
        return self._values is not None

    @property
    def get(self):
        return self._values

    def update(self, values):
        self._values = values

    def setTimeoutTimestamp(self, timestamp_ms):
        self.timeout_timestamp = timestamp_ms

    def getCurrentWatermarkMs(self):
        return self._watermark_ms


# ---------------------------------------------------------------------------
# Critical fill - the collection list
# ---------------------------------------------------------------------------


def test_a_bin_over_the_threshold_goes_on_the_collection_list():
    memory = fresh_memory()

    assert "CRITICAL_FILL" in feed(memory, reading(fill_pct=85.0))


def test_a_bin_under_the_threshold_does_not():
    memory = fresh_memory()

    assert "CRITICAL_FILL" not in feed(memory, reading(fill_pct=79.0))


def test_critical_fill_fires_once_not_on_every_reading():
    """The client asked for a collection list, not a stream of the same fact.

    A bare filter would re-fire every few seconds for as long as the bin stayed
    full - one bin stuck at 88% producing hundreds of identical alerts an hour.
    """
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=85.0, event_ms=START_MS),
        reading(fill_pct=86.0, event_ms=START_MS + minutes(1)),
        reading(fill_pct=87.0, event_ms=START_MS + minutes(2)),
        reading(fill_pct=88.0, event_ms=START_MS + minutes(3)),
    )

    assert fired.count("CRITICAL_FILL") == 1


def test_critical_fill_can_fire_again_after_a_collection():
    """Clearing on collection is what makes firing once safe."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=85.0, event_ms=START_MS),
        reading(fill_pct=5.0, event_ms=START_MS + minutes(1)),
        reading(fill_pct=85.0, event_ms=START_MS + minutes(60)),
    )

    assert fired.count("CRITICAL_FILL") == 2


# ---------------------------------------------------------------------------
# Overflow
# ---------------------------------------------------------------------------


def test_an_overflowing_bin_is_reported():
    memory = fresh_memory()

    assert "OVERFLOW" in feed(memory, reading(fill_pct=97.0))


def test_a_merely_critical_bin_is_not_reported_as_overflowing():
    memory = fresh_memory()

    assert "OVERFLOW" not in feed(memory, reading(fill_pct=85.0))


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def test_a_large_drop_is_a_collection():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=90.0, event_ms=START_MS),
        reading(fill_pct=5.0, event_ms=START_MS + minutes(1)),
    )

    assert "COLLECTED" in fired


def test_a_small_drop_is_not_a_collection():
    """Sensor noise and partial removals are not the truck arriving."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=50.0, event_ms=START_MS),
        reading(fill_pct=45.0, event_ms=START_MS + minutes(1)),
    )

    assert "COLLECTED" not in fired


def test_a_drop_from_a_low_level_is_not_a_collection():
    """A bin that was never full cannot have been emptied by a truck."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=30.0, event_ms=START_MS),
        reading(fill_pct=2.0, event_ms=START_MS + minutes(1)),
    )

    assert "COLLECTED" not in fired


# ---------------------------------------------------------------------------
# Abnormal jump
# ---------------------------------------------------------------------------


def test_a_sudden_rise_is_flagged():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=20.0, event_ms=START_MS),
        reading(fill_pct=70.0, event_ms=START_MS + minutes(1)),
    )

    assert "ANOMALY_JUMP" in fired


def test_normal_filling_is_not_flagged():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=20.0, event_ms=START_MS),
        reading(fill_pct=21.0, event_ms=START_MS + minutes(1)),
    )

    assert "ANOMALY_JUMP" not in fired


def test_the_first_ever_reading_is_never_a_jump():
    """With nothing to compare against, a full bin is not a sudden rise."""
    memory = fresh_memory()

    assert "ANOMALY_JUMP" not in feed(memory, reading(fill_pct=95.0))


# ---------------------------------------------------------------------------
# Stuck sensor
# ---------------------------------------------------------------------------


def test_a_frozen_reading_is_eventually_reported():
    memory = fresh_memory()
    same = [
        reading(fill_pct=42.0, event_ms=START_MS + minutes(index))
        for index in range(settings.STUCK_READING_COUNT + 2)
    ]

    assert "SENSOR_STUCK" in feed(memory, *same)


def test_a_stuck_sensor_is_reported_once_not_forever():
    memory = fresh_memory()
    same = [
        reading(fill_pct=42.0, event_ms=START_MS + minutes(index))
        for index in range(settings.STUCK_READING_COUNT * 3)
    ]

    assert feed(memory, *same).count("SENSOR_STUCK") == 1


def test_a_bin_that_keeps_moving_is_not_stuck():
    memory = fresh_memory()
    moving = [
        reading(fill_pct=10.0 + index, event_ms=START_MS + minutes(index))
        for index in range(settings.STUCK_READING_COUNT * 2)
    ]

    assert "SENSOR_STUCK" not in feed(memory, *moving)


# ---------------------------------------------------------------------------
# Fire risk
# ---------------------------------------------------------------------------


def test_a_hot_full_bin_is_a_fire_risk():
    memory = fresh_memory()

    assert "FIRE_RISK" in feed(memory, reading(temperature=85.0, fill_pct=90.0))


def test_a_hot_empty_bin_is_not_a_fire_risk():
    """A hot empty bin is a warm day."""
    memory = fresh_memory()

    assert "FIRE_RISK" not in feed(memory, reading(temperature=85.0, fill_pct=10.0))


def test_a_full_cool_bin_is_not_a_fire_risk():
    """A full cool bin is just a full bin."""
    memory = fresh_memory()

    assert "FIRE_RISK" not in feed(memory, reading(temperature=25.0, fill_pct=95.0))


def test_fire_risk_repeats_while_it_stays_true():
    """Unlike the fire-once alerts: a fire does not stop being urgent.

    It is still rate limited, so it does not fire on every reading.
    """
    memory = fresh_memory()
    hot = [
        reading(
            temperature=85.0,
            fill_pct=90.0,
            event_ms=START_MS + minutes(index * settings.FIRE_RISK_REPEAT_MINUTES),
        )
        for index in range(4)
    ]

    assert feed(memory, *hot).count("FIRE_RISK") == 4


def test_fire_risk_is_rate_limited_between_repeats():
    memory = fresh_memory()
    hot = [
        reading(temperature=85.0, fill_pct=90.0, event_ms=START_MS + index * 5000)
        for index in range(20)
    ]

    assert feed(memory, *hot).count("FIRE_RISK") == 1


# ---------------------------------------------------------------------------
# Low battery
# ---------------------------------------------------------------------------


def test_a_flat_battery_is_reported():
    memory = fresh_memory()

    assert "LOW_BATTERY" in feed(memory, reading(battery_level=15.0))


def test_a_healthy_battery_is_not_reported():
    memory = fresh_memory()

    assert "LOW_BATTERY" not in feed(memory, reading(battery_level=50.0))


def test_low_battery_fires_once_while_it_stays_low():
    """Battery only falls, so without this it would alert until replaced."""
    memory = fresh_memory()
    draining = [
        reading(battery_level=19.0 - index, event_ms=START_MS + minutes(index))
        for index in range(10)
    ]

    assert feed(memory, *draining).count("LOW_BATTERY") == 1


def test_low_battery_can_fire_again_after_a_replacement():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(battery_level=15.0, event_ms=START_MS),
        reading(battery_level=100.0, event_ms=START_MS + minutes(1)),
        reading(battery_level=15.0, event_ms=START_MS + minutes(2)),
    )

    assert fired.count("LOW_BATTERY") == 2


# ---------------------------------------------------------------------------
# Overflow prediction
# ---------------------------------------------------------------------------


def test_a_fast_filling_bin_is_predicted_to_overflow():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=30.0, event_ms=START_MS),
        reading(fill_pct=55.0, event_ms=START_MS + minutes(10)),
    )

    assert "PREDICTED_OVERFLOW" in fired


def test_a_slow_filling_bin_is_not():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=30.0, event_ms=START_MS),
        reading(fill_pct=30.5, event_ms=START_MS + minutes(10)),
    )

    assert "PREDICTED_OVERFLOW" not in fired


def test_an_emptying_bin_is_never_predicted_to_overflow():
    """A negative rate projects to a nonsensical time and must not be used."""
    rate, minutes_to_full = fill_projection(
        previous_pct=90.0,
        previous_ms=START_MS,
        fill_pct=10.0,
        event_ms=START_MS + minutes(5),
    )

    assert rate < 0
    assert minutes_to_full is None


def test_no_projection_from_a_single_reading():
    """A rate needs two readings; one is not a trend."""
    rate, minutes_to_full = fill_projection(None, 0, 50.0, START_MS)

    assert rate is None
    assert minutes_to_full is None


def test_the_projection_arithmetic_is_right():
    """Half full, rising two percent a minute, is full in twenty-five minutes."""
    rate, minutes_to_full = fill_projection(
        previous_pct=40.0,
        previous_ms=START_MS,
        fill_pct=50.0,
        event_ms=START_MS + minutes(5),
    )

    assert rate == pytest.approx(2.0)
    assert minutes_to_full == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# SLA clocks
# ---------------------------------------------------------------------------


def test_a_bin_left_uncollected_breaches_its_sla():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=85.0, event_ms=START_MS),
        reading(
            fill_pct=86.0,
            event_ms=START_MS + minutes(settings.SLA_CRITICAL_MINUTES + 10),
        ),
    )

    assert "SLA_BREACH" in fired


def test_a_bin_collected_in_time_does_not():
    """The clock is cleared by the collection, not by the bin emptying itself."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=85.0, event_ms=START_MS),
        reading(fill_pct=5.0, event_ms=START_MS + minutes(10)),
        reading(
            fill_pct=20.0,
            event_ms=START_MS + minutes(settings.SLA_CRITICAL_MINUTES + 30),
        ),
    )

    assert "SLA_BREACH" not in fired


def test_an_overflowing_bin_is_on_a_shorter_clock():
    """Overflow gets thirty minutes where critical gets two hours."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=97.0, event_ms=START_MS),
        reading(
            fill_pct=98.0,
            event_ms=START_MS + minutes(settings.SLA_OVERFLOW_MINUTES + 5),
        ),
    )

    assert "SLA_BREACH" in fired


def test_an_sla_breach_is_reported_once():
    memory = fresh_memory()
    late = [
        reading(
            fill_pct=85.0,
            event_ms=START_MS + minutes(settings.SLA_CRITICAL_MINUTES + index * 10),
        )
        for index in range(1, 6)
    ]

    fired = feed(memory, reading(fill_pct=85.0, event_ms=START_MS), *late)

    assert fired.count("SLA_BREACH") == 1


# ---------------------------------------------------------------------------
# The operator as a whole
# ---------------------------------------------------------------------------


def as_frame(*readings):
    """Readings shaped as the pandas frame Spark hands the operator."""
    return pd.DataFrame(
        [
            {
                "bin_id": BIN,
                "zone": values["zone"],
                "capacity": values["capacity"],
                "current_fill_level": values["current_fill_level"],
                "fill_pct": values["fill_pct"],
                "battery_level": values["battery_level"],
                "temperature": values["temperature"],
                "latitude": values["latitude"],
                "longitude": values["longitude"],
                "event_time": pd.Timestamp(values["event_ms"], unit="ms", tz="UTC"),
            }
            for values in readings
        ]
    )


def run_operator(state, *readings):
    frames = [as_frame(*readings)] if readings else []
    return pd.concat(list(track_bin((BIN,), iter(frames), state)), ignore_index=True)


def test_the_operator_emits_one_state_row_per_batch():
    """Downstream needs exactly one current-state row per bin, not one per event."""
    state = FakeGroupState()

    out = run_operator(
        state,
        reading(fill_pct=10.0, event_ms=START_MS),
        reading(fill_pct=12.0, event_ms=START_MS + minutes(1)),
        reading(fill_pct=14.0, event_ms=START_MS + minutes(2)),
    )

    assert (out.record_type == RECORD_STATE).sum() == 1


def test_the_state_row_carries_the_latest_reading():
    state = FakeGroupState()

    out = run_operator(
        state,
        reading(fill_pct=10.0, event_ms=START_MS),
        reading(fill_pct=14.0, event_ms=START_MS + minutes(2)),
    )

    latest = out[out.record_type == RECORD_STATE].iloc[0]
    assert latest["fill_pct"] == 14.0


def test_events_are_processed_in_time_order():
    """Out of order, a rise reads as a drop and a collection is invented.

    Spark makes no ordering promise within a batch, so the operator sorts.
    """
    state = FakeGroupState()

    out = run_operator(
        state,
        reading(fill_pct=5.0, event_ms=START_MS + minutes(2)),
        reading(fill_pct=90.0, event_ms=START_MS),
    )

    alerts = set(out[out.record_type == RECORD_ALERT].alert_type)
    assert "COLLECTED" in alerts

    latest = out[out.record_type == RECORD_STATE].iloc[0]
    assert latest["fill_pct"] == 5.0


def test_the_operator_arms_the_offline_timeout():
    """Every batch re-arms the timer that becomes the offline alert."""
    state = FakeGroupState()

    run_operator(state, reading(event_ms=START_MS))

    expected = START_MS + settings.OFFLINE_AFTER_MINUTES * 60_000
    assert state.timeout_timestamp == expected


def test_the_timeout_is_never_set_behind_the_watermark():
    """Spark rejects a timeout already in the past, which a late event asks for."""
    watermark = START_MS + minutes(600)
    state = FakeGroupState(watermark_ms=watermark)

    run_operator(state, reading(event_ms=START_MS))

    assert state.timeout_timestamp > watermark


def test_a_silent_bin_is_reported_offline():
    """Dead-device detection is the timer firing, not a rule matching."""
    memory = fresh_memory()
    memory["zone"] = "CENTRAL"
    memory["last_event_ms"] = START_MS
    memory["last_fill_pct"] = 42.0
    state = FakeGroupState(
        values=tuple(memory[name] for name in STATE_FIELDS), timed_out=True
    )

    out = run_operator(state)

    assert list(out.alert_type) == ["OFFLINE"]
    assert out.iloc[0]["zone"] == "CENTRAL"


def test_an_offline_alert_says_when_the_bin_was_last_seen():
    """The useful part of the alert: not that it is gone, but since when."""
    memory = fresh_memory()
    memory["last_event_ms"] = START_MS
    state = FakeGroupState(
        values=tuple(memory[name] for name in STATE_FIELDS), timed_out=True
    )

    out = run_operator(state)

    assert out.iloc[0]["last_seen"] == pd.Timestamp(START_MS, unit="ms", tz="UTC")


def test_state_survives_a_round_trip_through_storage():
    """What is written is what is read back, in the same order.

    The state is a positional tuple, so a field added to the schema without the
    dictionary matching would silently shift every value one place.
    """
    state = FakeGroupState()
    run_operator(state, reading(fill_pct=61.0, event_ms=START_MS))

    restored = dict(zip(STATE_FIELDS, state.get))

    assert restored["last_fill_pct"] == 61.0
    assert restored["zone"] == "CENTRAL"
    assert restored["last_event_ms"] == START_MS


def test_output_rows_match_the_declared_schema():
    """Every emitted column is one Spark is expecting."""
    state = FakeGroupState()

    out = run_operator(state, reading(fill_pct=85.0))

    assert list(out.columns) == OUTPUT_SCHEMA.fieldNames()
