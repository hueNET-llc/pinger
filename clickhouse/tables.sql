-- PLEASE NOTE
-- The buffer tables are what I personally use to buffer and batch inserts
-- You may have to modify them to work in your setup

CREATE TABLE pinger (
    type LowCardinality(String),
    host_country LowCardinality(Nullable(String)),
    host_state LowCardinality(Nullable(String)),
    host_city LowCardinality(Nullable(String)),
    host_name LowCardinality(String),
    host_asn Nullable(int),
    target_name LowCardinality(String),
    target_country LowCardinality(Nullable(String)),
    target_state LowCardinality(Nullable(String)),
    target_city LowCardinality(Nullable(String)),
    target_asn Nullable(int),
    target_ip LowCardinality(String),
    avg_ms Nullable(Float),
    max_ms Nullable(Float),
    min_ms Nullable(Float),
    loss_percent Float,
    time DateTime DEFAULT now()
) ENGINE = MergeTree() PARTITION BY toDate(time) ORDER BY (host_country, host_state, host_city, host_name, time) PRIMARY KEY (host_country, host_state, host_city, host_name, time);

CREATE TABLE pinger_buffer (
    type LowCardinality(String),
    host_country LowCardinality(Nullable(String)),
    host_state LowCardinality(Nullable(String)),
    host_city LowCardinality(Nullable(String)),
    host_name LowCardinality(String),
    host_asn Nullable(int),
    target_name LowCardinality(String),
    target_country LowCardinality(Nullable(String)),
    target_state LowCardinality(Nullable(String)),
    target_city LowCardinality(Nullable(String)),
    target_asn Nullable(int),
    target_ip LowCardinality(String),
    avg_ms Nullable(Float),
    max_ms Nullable(Float),
    min_ms Nullable(Float),
    loss_percent Float,
    time DateTime DEFAULT now()
) ENGINE = Buffer(homelab, pinger, 1, 10, 10, 10, 100, 10000, 10000);
