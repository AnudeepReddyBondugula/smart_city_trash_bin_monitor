-- Schema definitions for Smart City Trash Bin Monitor

CREATE TABLE IF NOT EXISTS api_users (
    username VARCHAR(50) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS ward_bins (
    ward INT NOT NULL,
    bin_id VARCHAR(50) NOT NULL,
    PRIMARY KEY (ward, bin_id)
);

CREATE TABLE IF NOT EXISTS valid_trash_bin_events (
    bin_id VARCHAR(50) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    ward INT NOT NULL,
    fill_level INT NOT NULL,
    temperature DOUBLE PRECISION,
    humidity INT,
    event_time TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (bin_id, event_time)
);

CREATE TABLE IF NOT EXISTS invalid_trash_bin_events (
    id SERIAL PRIMARY KEY,
    bin_id VARCHAR(50),
    raw_payload JSONB,
    error_reason TEXT,
    event_time TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_invalid_event UNIQUE (bin_id, event_time)
);

CREATE TABLE IF NOT EXISTS ward_fill_level_agg (
    ward INT NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    avg_fill_level DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (ward, window_start, window_end)
);

CREATE TABLE IF NOT EXISTS ward_fill_level_risk_agg (
    ward INT NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    avg_fill_level DOUBLE PRECISION NOT NULL,
    max_fill_level INT NOT NULL,
    min_fill_level INT NOT NULL,
    bins_above_80 INT NOT NULL,
    PRIMARY KEY (ward, window_start, window_end)
);

CREATE OR REPLACE VIEW ward_latest_fill_level AS
SELECT DISTINCT ON (ward)
    ward,
    window_start,
    window_end,
    avg_fill_level
FROM ward_fill_level_agg
ORDER BY ward, window_end DESC;
