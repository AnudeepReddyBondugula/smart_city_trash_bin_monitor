-- Analytical tables written by the stream processor and read by the APIs.
--
-- This file is the storage contract. It is applied at startup and is written to
-- be safe to re-run, so a restart never destroys accumulated history.
--
-- These tables are deliberately NOT part of the data-simulator Alembic chain.
-- That chain describes the simulator's own operational table, and the two are
-- owned by different services with different lifecycles; folding analytical
-- output into it would make either service unable to migrate without the other.
--
-- Every table carries a primary key that a re-run of the same batch collides
-- with. Spark re-runs a batch after a failed write, so writes have to be safe to
-- repeat: an append-only table would silently double-count on every retry.

-- ---------------------------------------------------------------------------
-- bin_alerts - one row per alert or collection event
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bin_alerts (
    bin_id        TEXT             NOT NULL,
    zone          TEXT             NOT NULL,
    alert_type    TEXT             NOT NULL,
    severity      TEXT             NOT NULL,
    fired_at      TIMESTAMPTZ      NOT NULL,
    fill_pct      DOUBLE PRECISION,
    temperature   DOUBLE PRECISION,
    battery_level DOUBLE PRECISION,
    detail        TEXT,
    -- The natural key of an alert. Re-processing a batch produces the identical
    -- row, which is then discarded rather than duplicated.
    PRIMARY KEY (bin_id, alert_type, fired_at)
);

CREATE INDEX IF NOT EXISTS bin_alerts_fired_at_idx
    ON bin_alerts (fired_at DESC);
CREATE INDEX IF NOT EXISTS bin_alerts_type_fired_at_idx
    ON bin_alerts (alert_type, fired_at DESC);
CREATE INDEX IF NOT EXISTS bin_alerts_zone_idx
    ON bin_alerts (zone, fired_at DESC);

-- ---------------------------------------------------------------------------
-- bin_state_latest - the current state of every bin, one row each
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bin_state_latest (
    bin_id                TEXT PRIMARY KEY,
    zone                  TEXT             NOT NULL,
    capacity              DOUBLE PRECISION,
    current_fill_level    DOUBLE PRECISION,
    fill_pct              DOUBLE PRECISION,
    temperature           DOUBLE PRECISION,
    battery_level         DOUBLE PRECISION,
    latitude              DOUBLE PRECISION,
    longitude             DOUBLE PRECISION,
    -- Rate of change between the last two readings, and the projection built
    -- from it. Null until a bin has reported twice.
    fill_rate_pct_per_min DOUBLE PRECISION,
    minutes_to_full       DOUBLE PRECISION,
    last_seen             TIMESTAMPTZ      NOT NULL,
    updated_at            TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS bin_state_latest_zone_idx
    ON bin_state_latest (zone);
CREATE INDEX IF NOT EXISTS bin_state_latest_last_seen_idx
    ON bin_state_latest (last_seen DESC);
CREATE INDEX IF NOT EXISTS bin_state_latest_fill_pct_idx
    ON bin_state_latest (fill_pct DESC);

-- ---------------------------------------------------------------------------
-- zone_metrics_5m - one zone over one five-minute window
-- ---------------------------------------------------------------------------
-- Hourly, daily, weekly and monthly figures are all SQL rollups of this table,
-- so streaming never has to hold more than five minutes of aggregate state.
CREATE TABLE IF NOT EXISTS zone_metrics_5m (
    window_start      TIMESTAMPTZ      NOT NULL,
    window_end        TIMESTAMPTZ      NOT NULL,
    zone              TEXT             NOT NULL,
    bins_reporting    INTEGER          NOT NULL,
    reading_count     BIGINT           NOT NULL,
    avg_fill_pct      DOUBLE PRECISION,
    max_fill_pct      DOUBLE PRECISION,
    avg_temperature   DOUBLE PRECISION,
    max_temperature   DOUBLE PRECISION,
    critical_readings BIGINT           NOT NULL DEFAULT 0,
    overflow_readings BIGINT           NOT NULL DEFAULT 0,
    PRIMARY KEY (window_start, zone)
);

CREATE INDEX IF NOT EXISTS zone_metrics_5m_window_idx
    ON zone_metrics_5m (window_start DESC);

-- ---------------------------------------------------------------------------
-- Nightly rollups - written by the batch job, not by any streaming query
-- ---------------------------------------------------------------------------
-- When waste is generated fastest, by zone and hour of day.
CREATE TABLE IF NOT EXISTS zone_hourly_profile (
    zone                   TEXT             NOT NULL,
    hour_of_day            SMALLINT         NOT NULL,
    avg_fill_rate_pct_hour DOUBLE PRECISION,
    avg_fill_pct           DOUBLE PRECISION,
    reading_count          BIGINT,
    computed_at            TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (zone, hour_of_day)
);

-- Longer-range trends, one row per zone per day.
CREATE TABLE IF NOT EXISTS zone_daily_trend (
    zone                   TEXT             NOT NULL,
    day                    DATE             NOT NULL,
    avg_fill_pct           DOUBLE PRECISION,
    max_fill_pct           DOUBLE PRECISION,
    avg_temperature        DOUBLE PRECISION,
    avg_fill_rate_pct_hour DOUBLE PRECISION,
    bins_reporting         INTEGER,
    collections            BIGINT,
    computed_at            TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (zone, day)
);

CREATE INDEX IF NOT EXISTS zone_daily_trend_day_idx
    ON zone_daily_trend (day DESC);

-- ---------------------------------------------------------------------------
-- city_kpi - the dashboard headline numbers
-- ---------------------------------------------------------------------------
-- Every one of these is an aggregate of the three tables above, so the
-- dashboard costs no streaming work of its own. A bin counts as active if it
-- has reported inside the offline threshold, which is the same 15 minutes the
-- dead-device rule uses; anything older is what "offline" means here.
CREATE OR REPLACE VIEW city_kpi AS
SELECT
    (SELECT count(*) FROM bin_state_latest)                             AS total_bins,
    (SELECT count(*) FROM bin_state_latest
      WHERE last_seen > now() - INTERVAL '15 minutes')                  AS active_bins,
    (SELECT count(*) FROM bin_state_latest
      WHERE last_seen <= now() - INTERVAL '15 minutes')                 AS offline_bins,
    (SELECT count(*) FROM bin_state_latest WHERE fill_pct >= 80)        AS critical_bins,
    (SELECT count(*) FROM bin_state_latest WHERE fill_pct >= 95)        AS overflowing_bins,
    (SELECT count(*) FROM bin_state_latest WHERE battery_level < 20)    AS low_battery_bins,
    (SELECT round(avg(fill_pct)::numeric, 2) FROM bin_state_latest)     AS avg_fill_pct,
    (SELECT round(avg(temperature)::numeric, 2) FROM bin_state_latest)  AS avg_temperature,
    (SELECT count(*) FROM bin_alerts
      WHERE fired_at >= date_trunc('day', now()))                       AS alerts_today,
    (SELECT count(*) FROM bin_alerts
      WHERE alert_type = 'COLLECTED'
        AND fired_at >= date_trunc('day', now()))                       AS collections_today,
    (SELECT count(*) FROM bin_alerts
      WHERE alert_type = 'FIRE_RISK'
        AND fired_at >= date_trunc('day', now()))                       AS fire_risk_today,
    (SELECT count(*) FROM bin_alerts
      WHERE alert_type = 'SLA_BREACH'
        AND fired_at >= date_trunc('day', now()))                       AS sla_breaches_today,
    (SELECT count(DISTINCT zone) FROM bin_state_latest)                 AS zones_covered;

-- The busiest zones, by how full their bins currently are.
CREATE OR REPLACE VIEW zone_leaderboard AS
SELECT
    zone,
    count(*)                                  AS bins,
    round(avg(fill_pct)::numeric, 2)          AS avg_fill_pct,
    count(*) FILTER (WHERE fill_pct >= 80)    AS critical_bins,
    round(avg(temperature)::numeric, 2)       AS avg_temperature
FROM bin_state_latest
GROUP BY zone
ORDER BY avg_fill_pct DESC;
