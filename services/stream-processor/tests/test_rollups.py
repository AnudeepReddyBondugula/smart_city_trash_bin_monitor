"""Tests for the rollup job.

These run on batch DataFrames because the job itself is batch - there is nothing
to simulate. The window function is the part worth checking carefully: it
compares each reading against the previous one for the same bin, and getting
either the partitioning or the ordering wrong produces numbers that look
plausible and are wrong.
"""

import datetime

import pytest

from batch.rollups import daily_trend, hourly_profile, with_fill_rate

SCHEMA = (
    "bin_id string, zone string, fill_pct double, temperature double, "
    "event_time timestamp"
)


def at(hour, minute=0, day=22):
    return datetime.datetime(2026, 8, day, hour, minute, tzinfo=datetime.timezone.utc)


def by_fill(rows):
    """Index collected rows by their fill level.

    Keyed on fill level rather than on the timestamp because Spark returns
    timestamps as naive datetimes in the driver's local zone, so comparing them
    against the tz-aware values used to build the input silently matches
    nothing.
    """
    return {row["fill_pct"]: row for row in rows}


@pytest.fixture
def history(spark):
    """Build an event history from (bin, zone, fill_pct, temperature, time)."""

    def build(rows):
        return spark.createDataFrame(rows, SCHEMA)

    return build


# ---------------------------------------------------------------------------
# Fill rate
# ---------------------------------------------------------------------------


def test_fill_rate_is_per_hour(history):
    """Ten percent over two hours is five percent an hour."""
    rated = with_fill_rate(
        history(
            [
                ("BIN-A", "CENTRAL", 10.0, 25.0, at(1)),
                ("BIN-A", "CENTRAL", 20.0, 25.0, at(3)),
            ]
        )
    ).collect()

    assert by_fill(rated)[20.0]["fill_rate_pct_hour"] == pytest.approx(5.0)


def test_the_first_reading_has_no_rate(history):
    """A rate needs two readings; one is not a trend."""
    rated = with_fill_rate(
        history([("BIN-A", "CENTRAL", 10.0, 25.0, at(1))])
    ).collect()

    assert rated[0]["fill_rate_pct_hour"] is None


def test_bins_are_never_compared_against_each_other(history):
    """The window is partitioned by bin.

    Without that, one bin's first reading is compared against another bin's
    last, inventing enormous rates out of nothing.
    """
    rated = with_fill_rate(
        history(
            [
                ("BIN-A", "CENTRAL", 90.0, 25.0, at(1)),
                ("BIN-B", "CENTRAL", 10.0, 25.0, at(2)),
            ]
        )
    ).collect()

    first_of_b = [row for row in rated if row["bin_id"] == "BIN-B"][0]
    assert first_of_b["fill_rate_pct_hour"] is None


def test_readings_are_compared_in_time_order(history):
    """Ordering is by event time, not by the order rows happen to be read."""
    rated = with_fill_rate(
        history(
            [
                ("BIN-A", "CENTRAL", 30.0, 25.0, at(5)),
                ("BIN-A", "CENTRAL", 10.0, 25.0, at(1)),
                ("BIN-A", "CENTRAL", 20.0, 25.0, at(3)),
            ]
        )
    ).collect()

    by_level = by_fill(rated)
    assert by_level[20.0]["prev_fill_pct"] == 10.0
    assert by_level[30.0]["prev_fill_pct"] == 20.0


def test_emptying_does_not_count_as_a_fill_rate(history):
    """A drop is the bin being collected, not it filling backwards.

    Averaging drops in would report the zones that are collected most often as
    the ones filling most slowly, which is exactly backwards.
    """
    rated = with_fill_rate(
        history(
            [
                ("BIN-A", "CENTRAL", 90.0, 25.0, at(1)),
                ("BIN-A", "CENTRAL", 5.0, 25.0, at(2)),
            ]
        )
    ).collect()

    assert by_fill(rated)[5.0]["fill_rate_pct_hour"] is None


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def test_a_large_drop_counts_as_a_collection(history):
    rated = with_fill_rate(
        history(
            [
                ("BIN-A", "CENTRAL", 90.0, 25.0, at(1)),
                ("BIN-A", "CENTRAL", 5.0, 25.0, at(2)),
            ]
        )
    ).collect()

    assert sum(row["collected"] for row in rated) == 1


def test_a_small_drop_does_not(history):
    rated = with_fill_rate(
        history(
            [
                ("BIN-A", "CENTRAL", 50.0, 25.0, at(1)),
                ("BIN-A", "CENTRAL", 45.0, 25.0, at(2)),
            ]
        )
    ).collect()

    assert sum(row["collected"] for row in rated) == 0


# ---------------------------------------------------------------------------
# Rollups
# ---------------------------------------------------------------------------


def test_hourly_profile_finds_the_busy_hour(history):
    """The point of the whole job: which hour a zone fills fastest."""
    rows = [
        ("BIN-A", "CENTRAL", 10.0, 25.0, at(3)),
        ("BIN-A", "CENTRAL", 12.0, 25.0, at(4)),  # +2 in an hour
        ("BIN-A", "CENTRAL", 42.0, 25.0, at(5)),  # +30 in an hour
    ]

    profile = {
        row["hour_of_day"]: row
        for row in hourly_profile(with_fill_rate(history(rows))).collect()
    }

    assert profile[5]["avg_fill_rate_pct_hour"] > profile[4]["avg_fill_rate_pct_hour"]


def test_hourly_profile_is_split_by_zone(history):
    rows = [
        ("BIN-A", "CENTRAL", 10.0, 25.0, at(3)),
        ("BIN-A", "CENTRAL", 12.0, 25.0, at(4)),
        ("BIN-B", "NORTH", 10.0, 25.0, at(3)),
        ("BIN-B", "NORTH", 40.0, 25.0, at(4)),
    ]

    zones = {row["zone"] for row in hourly_profile(with_fill_rate(history(rows))).collect()}

    assert zones == {"CENTRAL", "NORTH"}


def test_daily_trend_counts_distinct_bins_not_readings(history):
    """Two bins reporting five times each is two bins, not ten."""
    rows = [
        (f"BIN-{index % 2}", "CENTRAL", 10.0 + index, 25.0, at(1 + index))
        for index in range(10)
    ]

    day = daily_trend(with_fill_rate(history(rows))).collect()[0]

    assert day["bins_reporting"] == 2


def test_daily_trend_totals_collections(history):
    rows = [
        ("BIN-A", "CENTRAL", 90.0, 25.0, at(1)),
        ("BIN-A", "CENTRAL", 5.0, 25.0, at(2)),
        ("BIN-A", "CENTRAL", 95.0, 25.0, at(6)),
        ("BIN-A", "CENTRAL", 2.0, 25.0, at(7)),
    ]

    day = daily_trend(with_fill_rate(history(rows))).collect()[0]

    assert day["collections"] == 2


def test_daily_trend_separates_days(history):
    rows = [
        ("BIN-A", "CENTRAL", 10.0, 25.0, at(1, day=22)),
        ("BIN-A", "CENTRAL", 20.0, 25.0, at(1, day=23)),
    ]

    days = {str(row["day"]) for row in daily_trend(with_fill_rate(history(rows))).collect()}

    assert days == {"2026-08-22", "2026-08-23"}


def test_daily_trend_reports_the_peak_not_only_the_average(history):
    """An average hides the thing operations care about.

    A zone averaging 45% while one of its bins sat at 98% is not a calm zone.
    """
    rows = [
        ("BIN-A", "CENTRAL", 10.0, 25.0, at(1)),
        ("BIN-B", "CENTRAL", 98.0, 25.0, at(1)),
    ]

    day = daily_trend(with_fill_rate(history(rows))).collect()[0]

    assert day["avg_fill_pct"] == pytest.approx(54.0)
    assert day["max_fill_pct"] == pytest.approx(98.0)


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


def test_a_missing_history_is_not_a_failure(monkeypatch, tmp_path):
    """The first run happens before the streaming pipeline has written anything."""
    from batch import rollups

    monkeypatch.setattr(rollups.settings, "PARQUET_PATH", str(tmp_path / "absent"))
    monkeypatch.setattr(
        rollups, "build_session", lambda **_: pytest.fail("should not start Spark")
    )

    assert rollups.main() is None


def test_an_unreadable_history_fails_loudly(monkeypatch, tmp_path, spark):
    """Anything other than an absent directory has to reach the exit code.

    Reported as "no history" and exited zero, a corrupt or unreadable history
    left the analytical tables silently stale, with nothing for a scheduler to
    retry and nothing for monitoring to notice.
    """
    from batch import rollups

    history = tmp_path / "history"
    history.mkdir()
    (history / "part-0.parquet").write_text("this is not parquet")

    # The job stops its session in a finally, and the session here is shared
    # with every other test in the run - so it is handed one that ignores that.
    class KeepAlive:
        def __getattr__(self, name):
            return getattr(spark, name)

        def stop(self):
            pass

    monkeypatch.setattr(rollups.settings, "PARQUET_PATH", str(history))
    monkeypatch.setattr(rollups, "build_session", lambda **_: KeepAlive())

    with pytest.raises(Exception):
        rollups.main()
