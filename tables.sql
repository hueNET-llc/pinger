-- PLEASE NOTE
-- The buffer tables are what I personally use to buffer and batch inserts
-- You may have to modify them to work in your setup

CREATE TABLE pinger (
    host_name LowCardinality(String),
    target_name LowCardinality(String),
    target_ip LowCardinality(String),
    avg_ms Nullable(Float),
    max_ms Nullable(Float),
    min_ms Nullable(Float),
    loss_percent Float,
    time DateTime DEFAULT now()
) ENGINE = MergeTree() PARTITION BY toYYYYMM(time) ORDER BY (host_name, target_name, time) PRIMARY KEY (host_name, target_name, time);

CREATE TABLE pinger_buffer (
    host_name LowCardinality(String),
    target_name LowCardinality(String),
    target_ip LowCardinality(String),
    avg_ms Nullable(Float),
    max_ms Nullable(Float),
    min_ms Nullable(Float),
    loss_percent Float,
    time DateTime DEFAULT now()
) ENGINE = Buffer(homelab, pinger_targets, 1, 10, 10, 10, 100, 10000, 10000);
