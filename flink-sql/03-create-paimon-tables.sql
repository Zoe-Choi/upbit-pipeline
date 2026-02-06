-- ============================================================
-- Flink SQL: Paimon Sink Tables
-- Defines Paimon tables for storing Upbit market data
-- ============================================================

USE CATALOG paimon_catalog;
USE upbit;

-- ------------------------------------------------------------
-- Ticker Paimon Table (Changelog Mode)
-- Stores latest ticker snapshot per market
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticker (
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
    `ts` BIGINT,
    `stream_type` STRING,
    `ingested_at` STRING,
    `dt` STRING,  -- Partition key: date
    PRIMARY KEY (`market`, `dt`) NOT ENFORCED
) PARTITIONED BY (`dt`)
WITH (
    'merge-engine' = 'deduplicate',
    'changelog-producer' = 'input',
    'snapshot.time-retained' = '1 h',
    'snapshot.num-retained.min' = '5',
    'snapshot.num-retained.max' = '10',
    'write-buffer-size' = '64 mb',
    'page-size' = '64 kb'
);

-- ------------------------------------------------------------
-- Trade Paimon Table (Append Mode)
-- Stores all trade records for historical analysis
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade (
    `market` STRING,
    `trade_price` DOUBLE,
    `trade_volume` DOUBLE,
    `trade_value` DOUBLE,  -- Calculated: price * volume
    `ask_bid` STRING,
    `trade_date` STRING,
    `trade_time` STRING,
    `trade_timestamp` BIGINT,
    `ts` BIGINT,
    `prev_closing_price` DOUBLE,
    `change` STRING,
    `change_price` DOUBLE,
    `sequential_id` BIGINT,
    `stream_type` STRING,
    `ingested_at` STRING,
    `dt` STRING,  -- Partition key: date
    `hh` STRING,  -- Partition key: hour
    PRIMARY KEY (`market`, `sequential_id`, `dt`, `hh`) NOT ENFORCED
) PARTITIONED BY (`dt`, `hh`)
WITH (
    'merge-engine' = 'deduplicate',
    'changelog-producer' = 'input',
    'snapshot.time-retained' = '2 h',
    'snapshot.num-retained.min' = '10',
    'snapshot.num-retained.max' = '20',
    'write-buffer-size' = '128 mb'
);

-- ------------------------------------------------------------
-- Orderbook Paimon Table
-- Stores orderbook snapshots with flattened top levels
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orderbook (
    `market` STRING,
    `ts` BIGINT,
    `total_ask_size` DOUBLE,
    `total_bid_size` DOUBLE,
    `best_ask_price` DOUBLE,
    `best_bid_price` DOUBLE,
    `spread` DOUBLE,
    `spread_rate` DOUBLE,
    `stream_type` STRING,
    `ingested_at` STRING,
    `dt` STRING,
    PRIMARY KEY (`market`, `ts`, `dt`) NOT ENFORCED
) PARTITIONED BY (`dt`)
WITH (
    'merge-engine' = 'deduplicate',
    'changelog-producer' = 'input',
    'snapshot.time-retained' = '1 h',
    'write-buffer-size' = '64 mb'
);

-- ------------------------------------------------------------
-- OHLCV 1-Minute Aggregation Table
-- Pre-aggregated candlestick data
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ohlcv_1m (
    `market` STRING,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3),
    `open_price` DOUBLE,
    `high_price` DOUBLE,
    `low_price` DOUBLE,
    `close_price` DOUBLE,
    `volume` DOUBLE,
    `trade_count` BIGINT,
    `vwap` DOUBLE,  -- Volume Weighted Average Price
    `dt` STRING,
    `hh` STRING,
    PRIMARY KEY (`market`, `window_start`, `dt`, `hh`) NOT ENFORCED
) PARTITIONED BY (`dt`, `hh`)
WITH (
    'merge-engine' = 'deduplicate',
    'changelog-producer' = 'input',
    'snapshot.time-retained' = '24 h'
);

-- Verify tables created
SHOW TABLES;
