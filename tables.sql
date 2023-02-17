-- PLEASE NOTE
-- The buffer tables are what I personally use to buffer and batch inserts
-- You may have to modify them to work in your setup

CREATE TABLE pinger (
    name LowCardinality(String),
    ip LowCardinality(String),
    avg_ms Nullable(Float),
    max_ms Nullable(Float),
    min_ms Nullable(Float),
    loss_percent Float,
    time DateTime DEFAULT now()
) ENGINE = MergeTree() PARTITION BY toYYYYMM(time) ORDER BY (name, time) PRIMARY KEY (name, time);

CREATE TABLE pinger_buffer (
    name LowCardinality(String),
    ip LowCardinality(String),
    avg_ms Nullable(Float),
    max_ms Nullable(Float),
    min_ms Nullable(Float),
    loss_percent Float,
    time DateTime DEFAULT now()
) ENGINE = Buffer(homelab, pinger_targets, 1, 10, 10, 10, 100, 10000, 10000);
