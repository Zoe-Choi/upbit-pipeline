-- ============================================================
-- Flink SQL: Kafka Source Tables
-- Defines source tables reading from Upbit Kafka topics
-- ============================================================

-- Switch to default catalog for Kafka sources
USE CATALOG default_catalog;
USE default_database;

-- ------------------------------------------------------------
-- Ticker Source Table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kafka_ticker (
    `market` STRING,
    `trade_price` DOUBLE,
    `opening_price` DOUBLE,
    `high_price` DOUBLE,
    `low_price` DOUBLE,
    `prev_closing_price` DOUBLE,
    `change` STRING,
    `change_price` DOUBLE,
    `change_rate` DOUBLE,
    `signed_change_price` DOUBLE,
    `signed_change_rate` DOUBLE,
    `trade_volume` DOUBLE,
    `acc_trade_volume` DOUBLE,
    `acc_trade_volume_24h` DOUBLE,
    `acc_trade_price` DOUBLE,
    `acc_trade_price_24h` DOUBLE,
    `trade_date` STRING,
    `trade_time` STRING,
    `trade_timestamp` BIGINT,
    `ask_bid` STRING,
    `highest_52_week_price` DOUBLE,
    `highest_52_week_date` STRING,
    `lowest_52_week_price` DOUBLE,
    `lowest_52_week_date` STRING,
    `timestamp` BIGINT,
    `stream_type` STRING,
    `acc_ask_volume` DOUBLE,
    `acc_bid_volume` DOUBLE,
    `market_state` STRING,
    `market_warning` STRING,
    `_ingested_at` STRING,
    `_source` STRING,
    -- Watermark for event time processing
    `event_time` AS TO_TIMESTAMP_LTZ(`trade_timestamp`, 3),
    WATERMARK FOR `event_time` AS `event_time` - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-ticker',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'properties.group.id' = 'flink-ticker-consumer',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json',
    'json.fail-on-missing-field' = 'false',
    'json.ignore-parse-errors' = 'true'
);

-- ------------------------------------------------------------
-- Trade Source Table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kafka_trade (
    `market` STRING,
    `trade_price` DOUBLE,
    `trade_volume` DOUBLE,
    `ask_bid` STRING,
    `trade_date` STRING,
    `trade_time` STRING,
    `trade_timestamp` BIGINT,
    `timestamp` BIGINT,
    `prev_closing_price` DOUBLE,
    `change` STRING,
    `change_price` DOUBLE,
    `sequential_id` BIGINT,
    `stream_type` STRING,
    `_ingested_at` STRING,
    `_source` STRING,
    -- Watermark for event time processing
    `event_time` AS TO_TIMESTAMP_LTZ(`trade_timestamp`, 3),
    WATERMARK FOR `event_time` AS `event_time` - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-trade',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'properties.group.id' = 'flink-trade-consumer',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json',
    'json.fail-on-missing-field' = 'false',
    'json.ignore-parse-errors' = 'true'
);

-- ------------------------------------------------------------
-- Orderbook Source Table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kafka_orderbook (
    `market` STRING,
    `timestamp` BIGINT,
    `total_ask_size` DOUBLE,
    `total_bid_size` DOUBLE,
    `orderbook_units` ARRAY<ROW<
        `ask_price` DOUBLE,
        `bid_price` DOUBLE,
        `ask_size` DOUBLE,
        `bid_size` DOUBLE
    >>,
    `stream_type` STRING,
    `level` INT,
    `best_ask_price` DOUBLE,
    `best_bid_price` DOUBLE,
    `spread` DOUBLE,
    `spread_rate` DOUBLE,
    `_ingested_at` STRING,
    `_source` STRING,
    -- Watermark for event time processing
    `event_time` AS TO_TIMESTAMP_LTZ(`timestamp`, 3),
    WATERMARK FOR `event_time` AS `event_time` - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-orderbook',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'properties.group.id' = 'flink-orderbook-consumer',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json',
    'json.fail-on-missing-field' = 'false',
    'json.ignore-parse-errors' = 'true'
);

-- Verify tables created
SHOW TABLES;
