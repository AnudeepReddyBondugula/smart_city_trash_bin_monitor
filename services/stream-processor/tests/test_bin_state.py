"""Tests for Query 2 - the per-bin rules.

The rules are plain Python over a dictionary of remembered values, so they are
tested directly with no Spark session. That is deliberate: these twelve rules carry
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
        "sensor_faults": None,
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
# Broken sensors
# ---------------------------------------------------------------------------


def test_a_broken_sensor_is_reported():
    """The repair upstream must not be silent.

    A bin whose thermometer died has its temperature nulled so the bin stays
    trackable. Without this alert it would quietly stop contributing to fire
    risk with nobody told - the same blind spot as discarding it, only harder
    to see.
    """
    memory = fresh_memory()

    assert "SENSOR_FAULT" in feed(memory, reading(sensor_faults="temperature"))


def test_a_healthy_bin_reports_no_sensor_fault():
    memory = fresh_memory()

    assert "SENSOR_FAULT" not in feed(memory, reading())


def test_a_broken_sensor_is_reported_once_not_every_reading():
    """A permanently faulty sensor produces one alert, not a stream of them."""
    memory = fresh_memory()
    faulty = [
        reading(sensor_faults="temperature", event_ms=START_MS + minutes(index))
        for index in range(20)
    ]

    assert feed(memory, *faulty).count("SENSOR_FAULT") == 1


def test_a_sensor_fault_can_be_reported_again_after_a_repair():
    """Clearing when the sensor recovers is what makes firing once safe."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(sensor_faults="temperature", event_ms=START_MS),
        reading(event_ms=START_MS + minutes(1)),
        reading(sensor_faults="temperature", event_ms=START_MS + minutes(2)),
    )

    assert fired.count("SENSOR_FAULT") == 2


def test_a_bin_with_a_broken_sensor_is_still_tracked():
    """The whole point: it stays in the state store and keeps being watched.

    It must still reach critical fill, and still arm its offline timeout.
    """
    memory = fresh_memory()

    fired = feed(memory, reading(sensor_faults="temperature", fill_pct=85.0))

    assert "CRITICAL_FILL" in fired
    assert memory["last_fill_pct"] == 85.0


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

    assert "SLA_BREACH_CRITICAL" in fired


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

    assert not [alert for alert in fired if alert.startswith("SLA_BREACH")]


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

    assert "SLA_BREACH_OVERFLOW" in fired


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

    assert fired.count("SLA_BREACH_CRITICAL") == 1


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
                "sensor_faults": values["sensor_faults"],
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


# ---------------------------------------------------------------------------
# Regressions found in review
# ---------------------------------------------------------------------------


def test_wobbling_across_the_threshold_does_not_re_alert():
    """A dip below the line is not a collection, and must not read as one.

    Clearing the fire-once flag on any reading under the threshold meant a bin
    oscillating around 80% alerted on every crossing - and, worse, restarted
    the SLA clock each time, so a bin nobody ever collected could stay inside
    its SLA forever.
    """
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=81.0, event_ms=START_MS),
        reading(fill_pct=79.0, event_ms=START_MS + minutes(1)),
        reading(fill_pct=81.0, event_ms=START_MS + minutes(2)),
    )

    assert fired.count("CRITICAL_FILL") == 1
    assert memory["critical_since_ms"] == START_MS


def test_wobbling_across_the_threshold_does_not_postpone_an_sla_breach():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=81.0, event_ms=START_MS),
        reading(fill_pct=79.0, event_ms=START_MS + minutes(1)),
        reading(
            fill_pct=81.0,
            event_ms=START_MS + minutes(settings.SLA_CRITICAL_MINUTES + 5),
        ),
    )

    assert "SLA_BREACH_CRITICAL" in fired


def test_wobbling_across_the_overflow_threshold_behaves_the_same():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(fill_pct=96.0, event_ms=START_MS),
        reading(fill_pct=94.0, event_ms=START_MS + minutes(1)),
        reading(fill_pct=96.0, event_ms=START_MS + minutes(2)),
    )

    assert fired.count("OVERFLOW") == 1
    assert memory["overflow_since_ms"] == START_MS


def test_a_full_bin_is_not_a_stuck_sensor():
    """100% repeated is what a full bin looks like, not what a broken one does.

    The simulator caps fill at capacity, so every bin waiting for a truck
    reports exactly 100% each tick - the most ordinary state in the fleet, and
    it was being reported as a hardware fault.
    """
    memory = fresh_memory()
    full = [
        reading(fill_pct=100.0, event_ms=START_MS + minutes(index))
        for index in range(settings.STUCK_READING_COUNT + 5)
    ]

    assert "SENSOR_STUCK" not in feed(memory, *full)


def test_a_sensor_frozen_at_empty_is_still_reported():
    """Zero is not the mirror of 100%, and excluding it hid the FROZEN fault.

    A full bin repeats 100% because the level is clamped at capacity. Nothing
    clamps a bin at empty - waste accumulates - so a bin repeating 0% has a
    sensor that stopped. Bins are seeded empty, so excluding zero suppressed
    the alert for every frozen bin in the fleet, which an end-to-end run caught
    and the unit tests did not.
    """
    memory = fresh_memory()
    empty = [
        reading(fill_pct=0.0, event_ms=START_MS + minutes(index))
        for index in range(settings.STUCK_READING_COUNT + 5)
    ]

    assert "SENSOR_STUCK" in feed(memory, *empty)


def test_a_frozen_sensor_between_the_rails_is_still_reported():
    """The narrowing must not disable the detector it narrows."""
    memory = fresh_memory()
    same = [
        reading(fill_pct=42.0, event_ms=START_MS + minutes(index))
        for index in range(settings.STUCK_READING_COUNT + 2)
    ]

    assert "SENSOR_STUCK" in feed(memory, *same)


def test_both_sla_clocks_breaching_at_once_produce_distinct_alerts():
    """One alert type for both clocks collided in the database.

    bin_alerts keys on (bin_id, alert_type, fired_at) and both breaches carry
    the same event timestamp, so the second was silently discarded on insert.
    """
    memory = fresh_memory()
    later = START_MS + minutes(settings.SLA_CRITICAL_MINUTES + 5)

    evaluate_reading(memory, reading(fill_pct=97.0, event_ms=START_MS), BIN)
    alerts = evaluate_reading(memory, reading(fill_pct=98.0, event_ms=later), BIN)

    breaches = [alert for alert in alerts if alert["alert_type"].startswith("SLA_")]
    keys = {(alert["bin_id"], alert["alert_type"], alert["fired_at"]) for alert in breaches}

    assert len(breaches) == 2
    # Same instant, so only the alert type keeps them apart in the table.
    assert len({alert["fired_at"] for alert in breaches}) == 1
    assert len(keys) == 2


def test_a_second_failing_sensor_is_reported():
    """One boolean for every sensor hid the second failure entirely."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(sensor_faults="temperature", event_ms=START_MS),
        reading(
            sensor_faults="temperature,battery_level",
            event_ms=START_MS + minutes(1),
        ),
    )

    assert fired.count("SENSOR_FAULT") == 2


def test_the_same_failing_sensor_is_not_reported_twice():
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(sensor_faults="temperature", event_ms=START_MS),
        reading(sensor_faults="temperature", event_ms=START_MS + minutes(1)),
        reading(sensor_faults="temperature", event_ms=START_MS + minutes(2)),
    )

    assert fired.count("SENSOR_FAULT") == 1


def test_a_recovered_sensor_can_fail_again():
    """Recovery clears the name, so the next failure is news again."""
    memory = fresh_memory()

    fired = feed(
        memory,
        reading(sensor_faults="temperature", event_ms=START_MS),
        reading(sensor_faults=None, event_ms=START_MS + minutes(1)),
        reading(sensor_faults="temperature", event_ms=START_MS + minutes(2)),
    )

    assert fired.count("SENSOR_FAULT") == 2


def test_the_state_row_records_when_it_was_written():
    """updated_at is wall clock, last_seen is event time - both are needed.

    Omitted from the written columns it kept its insert default forever, so it
    reported when the bin was first seen and never moved again.
    """
    state = FakeGroupState()
    frame = pd.DataFrame(
        [
            {
                "bin_id": BIN,
                "zone": "CENTRAL",
                "capacity": 100.0,
                "current_fill_level": 50.0,
                "fill_pct": 50.0,
                "battery_level": 80.0,
                "temperature": 25.0,
                "latitude": 17.4,
                "longitude": 78.5,
                "sensor_faults": None,
                "event_time": pd.Timestamp(START_MS, unit="ms", tz="UTC"),
            }
        ]
    )

    rows = pd.concat(list(track_bin((BIN,), iter([frame]), state)))
    states = rows[rows["record_type"] == RECORD_STATE]

    assert len(states) == 1
    assert states.iloc[0]["updated_at"] is not None
