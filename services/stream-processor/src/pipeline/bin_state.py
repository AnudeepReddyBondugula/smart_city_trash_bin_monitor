"""Query 2 - one function that remembers each bin.

Eight of the client's fifteen problems ask the same underlying question: what did
this bin say last time, and how long ago? Critical fill, overflow prediction,
abnormal jumps, fire risk, dead devices, low battery, collection events, stuck
sensors and the SLA clocks all answer it. Handled separately they would be eight
queries each holding their own copy of the same per-bin memory.

Three of them - critical fill, fire risk and low battery - look like plain
filters. They are not. A bare filter re-fires for as long as the condition holds,
so one bin stuck at 88% produces an alert every few seconds forever. The client
asked for a collection list, not a stream of the same fact. Firing once on entry
and clearing on collection needs per-bin memory, which puts them here too.

So there is one stateful operator keyed by bin, reading and writing state once
per event, and emitting twelve kinds of alert from it.

Dead-device detection is the one rule that is not a rule at all: it is the
absence of events. Each event arms an event-time timeout, and when that fires
Spark calls this function with no data and it reports the bin offline.
"""

import logging
from datetime import datetime, timezone

import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql.streaming.state import GroupStateTimeout
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from config import get_settings
from schema import EVENT_TIME_COLUMN
from sinks import write_batch

logger = logging.getLogger(__name__)
settings = get_settings()

MINUTE_MS = 60_000

# Rows leaving the operator are of two kinds, distinguished by record_type: the
# alerts that fired, and the current state of the bin. They share one schema
# because an operator emits one shape, and the batch writer routes each kind to
# its own table.
RECORD_ALERT = "ALERT"
RECORD_STATE = "STATE"

OUTPUT_SCHEMA = StructType(
    [
        StructField("record_type", StringType()),
        StructField("bin_id", StringType()),
        StructField("zone", StringType()),
        StructField("alert_type", StringType()),
        StructField("severity", StringType()),
        StructField("fired_at", TimestampType()),
        StructField("detail", StringType()),
        StructField("capacity", DoubleType()),
        StructField("current_fill_level", DoubleType()),
        StructField("fill_pct", DoubleType()),
        StructField("temperature", DoubleType()),
        StructField("battery_level", DoubleType()),
        StructField("latitude", DoubleType()),
        StructField("longitude", DoubleType()),
        StructField("fill_rate_pct_per_min", DoubleType()),
        StructField("minutes_to_full", DoubleType()),
        StructField("sensor_faults", StringType()),
        StructField("last_seen", TimestampType()),
        # Wall-clock time this row was produced, as opposed to last_seen, which
        # is event time. The pair is what separates "this bin stopped
        # reporting" from "the pipeline stopped writing".
        StructField("updated_at", TimestampType()),
    ]
)

# What is remembered between events. Roughly two hundred bytes per bin, so about
# a megabyte for a five thousand bin city - small enough that the size of this
# is not the interesting constraint.
STATE_SCHEMA = StructType(
    [
        StructField("zone", StringType()),
        StructField("capacity", DoubleType()),
        StructField("last_fill_level", DoubleType()),
        StructField("last_fill_pct", DoubleType()),
        StructField("last_temperature", DoubleType()),
        StructField("last_battery", DoubleType()),
        StructField("latitude", DoubleType()),
        StructField("longitude", DoubleType()),
        StructField("last_event_ms", LongType()),
        # How many consecutive readings have been identical. A real bin's level
        # moves a little every reading, so a value that has not changed at all
        # for a long run has frozen.
        StructField("unchanged_count", IntegerType()),
        # When each SLA clock started, or 0 when it is not running. These are
        # what a collection clears.
        StructField("critical_since_ms", LongType()),
        StructField("overflow_since_ms", LongType()),
        # Which fire-once alerts are currently outstanding, so they are not
        # repeated every few seconds for as long as the condition holds.
        StructField("critical_fired", BooleanType()),
        StructField("overflow_fired", BooleanType()),
        StructField("low_battery_fired", BooleanType()),
        StructField("predicted_fired", BooleanType()),
        StructField("sla_critical_fired", BooleanType()),
        StructField("sla_overflow_fired", BooleanType()),
        # Which sensors were already reported broken, so a permanently faulty
        # one produces a single alert rather than a stream - while a second
        # sensor failing later is still news. A boolean here meant a bin whose
        # thermometer was already dead could lose its battery reading silently.
        StructField("reported_faults", StringType()),
        # Fire risk is the exception: it repeats while it stays true, because a
        # fire does not stop being urgent because it was already reported.
        StructField("last_fire_risk_ms", LongType()),
    ]
)

STATE_FIELDS = [field.name for field in STATE_SCHEMA.fields]

EMPTY_STATE = {
    "zone": None,
    "capacity": None,
    "last_fill_level": None,
    "last_fill_pct": None,
    "last_temperature": None,
    "last_battery": None,
    "latitude": None,
    "longitude": None,
    "last_event_ms": 0,
    "unchanged_count": 0,
    "critical_since_ms": 0,
    "overflow_since_ms": 0,
    "critical_fired": False,
    "overflow_fired": False,
    "low_battery_fired": False,
    "predicted_fired": False,
    "sla_critical_fired": False,
    "sla_overflow_fired": False,
    "reported_faults": None,
    "last_fire_risk_ms": 0,
}

SEVERITY = {
    "OVERFLOW": "CRITICAL",
    "FIRE_RISK": "CRITICAL",
    # Two clocks, two alert types. One shared type collided in the database:
    # both clocks can come due on the same reading, and the alert table keys on
    # (bin_id, alert_type, fired_at), so one of the two was silently discarded.
    "SLA_BREACH_OVERFLOW": "CRITICAL",
    "SLA_BREACH_CRITICAL": "CRITICAL",
    "CRITICAL_FILL": "HIGH",
    "PREDICTED_OVERFLOW": "HIGH",
    "OFFLINE": "HIGH",
    "SENSOR_STUCK": "MEDIUM",
    "ANOMALY_JUMP": "MEDIUM",
    "LOW_BATTERY": "MEDIUM",
    "SENSOR_FAULT": "MEDIUM",
    "COLLECTED": "INFO",
}


def read_state(state) -> dict:
    """The remembered values for this bin, or a blank slate for a new one."""
    if not state.exists:
        return dict(EMPTY_STATE)
    return dict(zip(STATE_FIELDS, state.get))


def write_state(state, values: dict) -> None:
    """Store the remembered values, in the order the schema declares."""
    state.update(tuple(values[name] for name in STATE_FIELDS))


def _alert(memory: dict, bin_id: str, alert_type: str, event_ms: int, detail: str):
    """Build one alert row from the bin's current state."""
    return {
        "record_type": RECORD_ALERT,
        "bin_id": bin_id,
        "zone": memory["zone"],
        "alert_type": alert_type,
        "severity": SEVERITY[alert_type],
        "fired_at": _to_timestamp(event_ms),
        "detail": detail,
        "capacity": memory["capacity"],
        "current_fill_level": memory["last_fill_level"],
        "fill_pct": memory["last_fill_pct"],
        "temperature": memory["last_temperature"],
        "battery_level": memory["last_battery"],
        "latitude": memory["latitude"],
        "longitude": memory["longitude"],
        "fill_rate_pct_per_min": None,
        "minutes_to_full": None,
        "sensor_faults": None,
        "last_seen": _to_timestamp(memory["last_event_ms"]),
        "updated_at": datetime.now(tz=timezone.utc),
    }


def _faults(names) -> set[str]:
    """The comma-separated fault names as a set, empty when there are none."""
    if not names:
        return set()
    return {name for name in names.split(",") if name}


def _to_timestamp(milliseconds) -> datetime | None:
    if not milliseconds:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def evaluate_reading(memory: dict, reading: dict, bin_id: str) -> list[dict]:
    """
    Fold one reading into the bin's memory and return the alerts it raised.

    Separated from the Spark plumbing so the rules can be read, and tested,
    without a cluster. `memory` is modified in place.
    """
    alerts = []

    event_ms = reading["event_ms"]
    fill_pct = reading["fill_pct"]
    previous_pct = memory["last_fill_pct"]
    previous_ms = memory["last_event_ms"]

    # Everything below reads the current values from memory, so update first and
    # let the rules describe the bin as it now is.
    memory["zone"] = reading["zone"]
    memory["capacity"] = reading["capacity"]
    memory["last_fill_level"] = reading["current_fill_level"]
    memory["last_fill_pct"] = fill_pct
    memory["last_temperature"] = reading["temperature"]
    memory["last_battery"] = reading["battery_level"]
    memory["latitude"] = reading["latitude"]
    memory["longitude"] = reading["longitude"]
    memory["last_event_ms"] = event_ms

    # ---- Collection --------------------------------------------------------
    # A large drop, not any drop. Requiring the bin to have been substantially
    # full first is what separates a truck emptying it from sensor noise, and it
    # is the event that clears both SLA clocks.
    collected = (
        previous_pct is not None
        and previous_pct >= settings.COLLECTION_DROP_FROM_PCT
        and fill_pct < settings.COLLECTION_DROP_TO_PCT
    )

    if collected:
        alerts.append(
            _alert(
                memory,
                bin_id,
                "COLLECTED",
                event_ms,
                f"emptied from {previous_pct:.1f}% to {fill_pct:.1f}%",
            )
        )
        memory["critical_since_ms"] = 0
        memory["overflow_since_ms"] = 0
        memory["critical_fired"] = False
        memory["overflow_fired"] = False
        memory["predicted_fired"] = False
        memory["sla_critical_fired"] = False
        memory["sla_overflow_fired"] = False

    # ---- Abnormal jump -----------------------------------------------------
    elif (
        previous_pct is not None
        and fill_pct - previous_pct >= settings.ANOMALY_JUMP_PCT
    ):
        alerts.append(
            _alert(
                memory,
                bin_id,
                "ANOMALY_JUMP",
                event_ms,
                f"rose {fill_pct - previous_pct:.1f}% between readings",
            )
        )

    # ---- Stuck sensor ------------------------------------------------------
    # Not while saturated. A full bin reports exactly 100% every few seconds
    # until a truck arrives, because the level is clamped at capacity and
    # physically cannot read higher - so identical readings there say nothing
    # about the sensor, and a full bin waiting for collection is the most
    # ordinary state in the fleet.
    #
    # The cost is that a sensor genuinely frozen at 100% is never reported.
    # That is not a gap worth closing: it is indistinguishable from a full bin.
    #
    # Zero is NOT the same case and is deliberately not excluded. Nothing
    # clamps a bin at empty - waste accumulates - so a bin repeating 0% is a
    # sensor that has stopped, which is exactly what the FROZEN fault produces
    # and what this rule is for.
    saturated = fill_pct >= 100

    if previous_pct is not None and fill_pct == previous_pct and not saturated:
        memory["unchanged_count"] += 1
    else:
        memory["unchanged_count"] = 0

    # Fires on the reading that crosses the threshold, not every reading after
    # it, so a permanently frozen sensor produces one alert rather than a stream.
    if memory["unchanged_count"] == settings.STUCK_READING_COUNT:
        alerts.append(
            _alert(
                memory,
                bin_id,
                "SENSOR_STUCK",
                event_ms,
                f"{memory['unchanged_count']} identical readings at "
                f"{fill_pct:.1f}%",
            )
        )

    # ---- Critical fill -----------------------------------------------------
    # Cleared by a collection and by nothing else. Clearing on any reading back
    # under the threshold looks equivalent and is not: a bin wobbling around
    # 80% re-alerts on every crossing and restarts its SLA clock each time, so
    # a bin nobody ever collects can stay permanently inside its SLA.
    if fill_pct >= settings.CRITICAL_FILL_PCT and not memory["critical_fired"]:
        alerts.append(
            _alert(
                memory,
                bin_id,
                "CRITICAL_FILL",
                event_ms,
                f"{fill_pct:.1f}% full",
            )
        )
        memory["critical_fired"] = True
        memory["critical_since_ms"] = event_ms

    # ---- Overflow ----------------------------------------------------------
    if fill_pct >= settings.OVERFLOW_FILL_PCT and not memory["overflow_fired"]:
        alerts.append(
            _alert(memory, bin_id, "OVERFLOW", event_ms, f"{fill_pct:.1f}% full")
        )
        memory["overflow_fired"] = True
        memory["overflow_since_ms"] = event_ms

    # ---- Predicted overflow ------------------------------------------------
    fill_rate, minutes_to_full = fill_projection(
        previous_pct, previous_ms, fill_pct, event_ms
    )

    if (
        minutes_to_full is not None
        and minutes_to_full <= 60
        and fill_pct < settings.CRITICAL_FILL_PCT
        and not memory["predicted_fired"]
    ):
        alerts.append(
            _alert(
                memory,
                bin_id,
                "PREDICTED_OVERFLOW",
                event_ms,
                f"full in about {minutes_to_full:.0f} minutes at "
                f"{fill_rate:.2f}%/min",
            )
        )
        memory["predicted_fired"] = True
    elif minutes_to_full is None or minutes_to_full > 60:
        memory["predicted_fired"] = False

    # ---- Fire risk ---------------------------------------------------------
    # Hot AND nearly full. Either alone is not an emergency: a hot empty bin is
    # a warm day, and a full cool bin is just a full bin.
    on_fire = (
        reading["temperature"] is not None
        and reading["temperature"] > settings.FIRE_RISK_TEMP_C
        and fill_pct > settings.FIRE_RISK_FILL_PCT
    )

    if on_fire:
        repeat_ms = settings.FIRE_RISK_REPEAT_MINUTES * MINUTE_MS
        if event_ms - memory["last_fire_risk_ms"] >= repeat_ms:
            alerts.append(
                _alert(
                    memory,
                    bin_id,
                    "FIRE_RISK",
                    event_ms,
                    f"{reading['temperature']:.1f} C at {fill_pct:.1f}% full",
                )
            )
            memory["last_fire_risk_ms"] = event_ms
    else:
        memory["last_fire_risk_ms"] = 0

    # ---- Low battery -------------------------------------------------------
    battery = reading["battery_level"]
    if battery is not None and battery < settings.LOW_BATTERY_PCT:
        if not memory["low_battery_fired"]:
            alerts.append(
                _alert(
                    memory,
                    bin_id,
                    "LOW_BATTERY",
                    event_ms,
                    f"battery at {battery:.1f}%",
                )
            )
            memory["low_battery_fired"] = True
    elif battery is not None:
        memory["low_battery_fired"] = False

    # ---- Broken sensors ----------------------------------------------------
    # A reading arrives with individual sensors already nulled out by the
    # cleaning step, which keeps the bin trackable when only one of them has
    # failed. Without an alert here that repair would be silent, and a bin whose
    # thermometer died would quietly stop contributing to fire risk with nobody
    # told - which is the same blind spot as discarding it, only harder to see.
    # Compared as a set of names rather than as "any fault at all", so a second
    # sensor failing while the first is still broken is reported. Recovery needs
    # no branch of its own: the remembered set is replaced by what this reading
    # says, so a name that stops appearing stops being outstanding.
    faults = reading.get("sensor_faults")
    new_faults = _faults(faults) - _faults(memory["reported_faults"])

    if new_faults:
        alerts.append(
            _alert(
                memory,
                bin_id,
                "SENSOR_FAULT",
                event_ms,
                f"unusable readings from: {','.join(sorted(new_faults))}",
            )
        )

    memory["reported_faults"] = faults or None

    # ---- SLA clocks --------------------------------------------------------
    alerts.extend(_sla_breaches(memory, bin_id, event_ms))

    return alerts


def _sla_breaches(memory: dict, bin_id: str, event_ms: int) -> list[dict]:
    """
    Alerts for bins left uncollected past the time the rules allow.

    The clocks start when the bin crosses each threshold and are cleared by a
    collection, so a breach means no truck came - not that the bin is full.
    """
    breaches = []

    clocks = (
        (
            "overflow_since_ms",
            "sla_overflow_fired",
            settings.SLA_OVERFLOW_MINUTES,
            "SLA_BREACH_OVERFLOW",
            "overflowing",
        ),
        (
            "critical_since_ms",
            "sla_critical_fired",
            settings.SLA_CRITICAL_MINUTES,
            "SLA_BREACH_CRITICAL",
            "critical",
        ),
    )

    for since_key, fired_key, allowed_minutes, alert_type, label in clocks:
        started = memory[since_key]
        if not started or memory[fired_key]:
            continue

        elapsed_minutes = (event_ms - started) / MINUTE_MS
        if elapsed_minutes > allowed_minutes:
            breaches.append(
                _alert(
                    memory,
                    bin_id,
                    alert_type,
                    event_ms,
                    f"{label} for {elapsed_minutes:.0f} minutes, "
                    f"allowed {allowed_minutes:.0f}",
                )
            )
            memory[fired_key] = True

    return breaches


def fill_projection(previous_pct, previous_ms, fill_pct, event_ms):
    """
    Rate of fill between two readings, and the minutes until full at that rate.

    Returns (None, None) until the bin has reported twice, and whenever it is
    not filling - a bin that just emptied has a negative rate, which projects to
    a nonsensical time and must not be reported as one.
    """
    if previous_pct is None or not previous_ms or event_ms <= previous_ms:
        return None, None

    elapsed_minutes = (event_ms - previous_ms) / MINUTE_MS
    if elapsed_minutes <= 0:
        return None, None

    rate = (fill_pct - previous_pct) / elapsed_minutes
    if rate <= 0:
        return rate, None

    return rate, (100 - fill_pct) / rate


def state_record(
    memory: dict, bin_id: str, fill_rate, minutes_to_full, sensor_faults=None
) -> dict:
    """The bin's current state, for the one-row-per-bin table."""
    return {
        "record_type": RECORD_STATE,
        "bin_id": bin_id,
        "zone": memory["zone"],
        "alert_type": None,
        "severity": None,
        "fired_at": None,
        "detail": None,
        "capacity": memory["capacity"],
        "current_fill_level": memory["last_fill_level"],
        "fill_pct": memory["last_fill_pct"],
        "temperature": memory["last_temperature"],
        "battery_level": memory["last_battery"],
        "latitude": memory["latitude"],
        "longitude": memory["longitude"],
        "fill_rate_pct_per_min": fill_rate,
        "minutes_to_full": minutes_to_full,
        "sensor_faults": sensor_faults,
        "last_seen": _to_timestamp(memory["last_event_ms"]),
        "updated_at": datetime.now(tz=timezone.utc),
    }


def track_bin(key, pdfs, state):
    """
    Handle every event that arrived for one bin in this batch, plus timeouts.

    Args:
        key:
            The grouping key, a one-element tuple of bin_id.

        pdfs:
            An iterator of pandas frames holding this bin's events. Empty when
            Spark is calling because the bin's timeout expired.

        state:
            The bin's remembered values, carried across batches.

    Yields:
        Alert rows and one current-state row, as pandas frames.
    """
    bin_id = key[0]
    memory = read_state(state)

    # The bin went quiet. This is dead-device detection: the absence of events,
    # noticed by a timer rather than by a rule, reporting when it was last seen.
    if state.hasTimedOut:
        silent_minutes = settings.OFFLINE_AFTER_MINUTES
        offline = _alert(
            memory,
            bin_id,
            "OFFLINE",
            memory["last_event_ms"] + int(silent_minutes * MINUTE_MS),
            f"no telemetry for {silent_minutes:.0f} minutes",
        )
        # State is kept, not removed, so the bin can be recognised as the same
        # bin if it starts reporting again.
        state.update(tuple(memory[name] for name in STATE_FIELDS))
        yield pd.DataFrame([offline])
        return

    alerts = []
    fill_rate = minutes_to_full = sensor_faults = None

    for pdf in pdfs:
        # Events for one bin can arrive in any order within a batch, and every
        # rule here compares against the previous reading. Out of order, a rise
        # reads as a drop and a collection is invented that never happened.
        for _, row in pdf.sort_values(EVENT_TIME_COLUMN).iterrows():
            previous_pct = memory["last_fill_pct"]
            previous_ms = memory["last_event_ms"]

            reading = {
                "zone": row["zone"],
                "capacity": _as_float(row["capacity"]),
                "current_fill_level": _as_float(row["current_fill_level"]),
                "fill_pct": _as_float(row["fill_pct"]),
                "temperature": _as_float(row["temperature"]),
                "battery_level": _as_float(row["battery_level"]),
                "latitude": _as_float(row["latitude"]),
                "longitude": _as_float(row["longitude"]),
                "sensor_faults": _as_text(row["sensor_faults"]),
                "event_ms": int(row[EVENT_TIME_COLUMN].timestamp() * 1000),
            }

            alerts.extend(evaluate_reading(memory, reading, bin_id))
            sensor_faults = reading["sensor_faults"]
            fill_rate, minutes_to_full = fill_projection(
                previous_pct, previous_ms, reading["fill_pct"], reading["event_ms"]
            )

    write_state(state, memory)

    # Arm the timeout that becomes the offline alert. Clamped above the current
    # watermark because Spark rejects a timeout already in the past, which is
    # what a late-arriving event would otherwise ask for.
    timeout_ms = memory["last_event_ms"] + int(
        settings.OFFLINE_AFTER_MINUTES * MINUTE_MS
    )
    state.setTimeoutTimestamp(max(timeout_ms, state.getCurrentWatermarkMs() + 1))

    rows = alerts + [
        state_record(memory, bin_id, fill_rate, minutes_to_full, sensor_faults)
    ]
    yield pd.DataFrame(rows, columns=OUTPUT_SCHEMA.fieldNames())


def _as_float(value):
    """Pandas nulls become None so they reach PostgreSQL as NULL, not NaN."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def _as_text(value):
    """Pandas nulls become None so an absent fault is falsy, not the string 'nan'."""
    if value is None or pd.isna(value):
        return None
    return str(value)


# ---------------------------------------------------------------------------
# Spark wiring
# ---------------------------------------------------------------------------

ALERT_COLUMNS = [
    "bin_id",
    "zone",
    "alert_type",
    "severity",
    "fired_at",
    "fill_pct",
    "temperature",
    "battery_level",
    "detail",
]

STATE_COLUMNS = [
    "bin_id",
    "zone",
    "capacity",
    "current_fill_level",
    "fill_pct",
    "temperature",
    "battery_level",
    "latitude",
    "longitude",
    "fill_rate_pct_per_min",
    "minutes_to_full",
    "sensor_faults",
    "last_seen",
    # Written explicitly. Left to the column default it recorded when the bin
    # was first seen and never moved again, since an upsert that does not name
    # a column does not touch it.
    "updated_at",
]


def evaluate(clean_events: DataFrame) -> DataFrame:
    """Run the stateful operator over the clean stream."""
    return clean_events.groupBy("bin_id").applyInPandasWithState(
        track_bin,
        outputStructType=OUTPUT_SCHEMA,
        stateStructType=STATE_SCHEMA,
        outputMode="append",
        timeoutConf=GroupStateTimeout.EventTimeTimeout,
    )


def _write(batch: DataFrame, batch_id: int) -> None:
    """
    Write one micro-batch: alerts appended, bin state replaced.

    The batch is cached because it is read twice, once for each destination, and
    without it the whole stateful computation would be re-run for the second
    read.
    """
    batch.persist()
    try:
        alerts = batch.filter(batch.record_type == RECORD_ALERT)
        # Alerts are facts about an instant and are never revised, so a retry of
        # this batch produces identical rows that are discarded rather than
        # duplicated.
        write_batch(
            alerts,
            "bin_alerts",
            ALERT_COLUMNS,
            ["bin_id", "alert_type", "fired_at"],
            mode="ignore",
        )

        states = batch.filter(batch.record_type == RECORD_STATE)
        write_batch(states, "bin_state_latest", STATE_COLUMNS, ["bin_id"], "upsert")
    finally:
        batch.unpersist()


def start(clean_events: DataFrame):
    """Start the per-bin alerting query."""
    return (
        evaluate(clean_events)
        .writeStream.outputMode("append")
        .foreachBatch(_write)
        .option("checkpointLocation", settings.checkpoint_for("bin_state"))
        .trigger(processingTime=settings.TRIGGER_INTERVAL)
        .queryName("bin_state")
        .start()
    )
