-- ============================================================
-- Flink SQL: Streaming Jobs
-- Defines continuous streaming jobs from Kafka to Paimon
-- ============================================================

-- Set execution mode to streaming
SET 'execution.runtime-mode' = 'streaming';
SET 'execution.checkpointing.interval' = '30s';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';

-- ------------------------------------------------------------
-- Job 1: Ticker Kafka to Paimon
-- ------------------------------------------------------------
INSERT INTO paimon_catalog.upbit.ticker
SELECT
    `market`,
    `trade_price`,
    `opening_price`,
    `high_price`,
    `low_price`,
    `prev_closing_price`,
    `change`,
    `change_price`,
    `change_rate`,
    `signed_change_price`,
    `signed_change_rate`,
    `trade_volume`,
    `acc_trade_volume`,
    `acc_trade_volume_24h`,
    `acc_trade_price`,
    `acc_trade_price_24h`,
    `trade_date`,
    `trade_time`,
    `trade_timestamp`,
    `ask_bid`,
    `highest_52_week_price`,
    `highest_52_week_date`,
    `lowest_52_week_price`,
    `lowest_52_week_date`,
    `timestamp` AS `ts`,
    `stream_type`,
    `_ingested_at` AS `ingested_at`,
    DATE_FORMAT(TO_TIMESTAMP_LTZ(`trade_timestamp`, 3), 'yyyy-MM-dd') AS `dt`
FROM default_catalog.default_database.kafka_ticker;

-- ------------------------------------------------------------
-- Job 2: Trade Kafka to Paimon
-- ------------------------------------------------------------
INSERT INTO paimon_catalog.upbit.trade
SELECT
    `market`,
    `trade_price`,
    `trade_volume`,
    `trade_price` * `trade_volume` AS `trade_value`,
    `ask_bid`,
    `trade_date`,
    `trade_time`,
    `trade_timestamp`,
    `timestamp` AS `ts`,
    `prev_closing_price`,
    `change`,
    `change_price`,
    `sequential_id`,
    `stream_type`,
    `_ingested_at` AS `ingested_at`,
    DATE_FORMAT(TO_TIMESTAMP_LTZ(`trade_timestamp`, 3), 'yyyy-MM-dd') AS `dt`,
    DATE_FORMAT(TO_TIMESTAMP_LTZ(`trade_timestamp`, 3), 'HH') AS `hh`
FROM default_catalog.default_database.kafka_trade;

-- ------------------------------------------------------------
-- Job 3: Orderbook Kafka to Paimon
-- ------------------------------------------------------------
INSERT INTO paimon_catalog.upbit.orderbook
SELECT
    `market`,
    `timestamp` AS `ts`,
    `total_ask_size`,
    `total_bid_size`,
    `best_ask_price`,
    `best_bid_price`,
    `spread`,
    `spread_rate`,
    `stream_type`,
    `_ingested_at` AS `ingested_at`,
    DATE_FORMAT(TO_TIMESTAMP_LTZ(`timestamp`, 3), 'yyyy-MM-dd') AS `dt`
FROM default_catalog.default_database.kafka_orderbook;

-- ------------------------------------------------------------
-- Job 4: 1-Minute OHLCV Aggregation
-- Aggregates trade data into 1-minute candles
-- ------------------------------------------------------------
INSERT INTO paimon_catalog.upbit.ohlcv_1m
SELECT
    `market`,
    TUMBLE_START(`event_time`, INTERVAL '1' MINUTE) AS `window_start`,
    TUMBLE_END(`event_time`, INTERVAL '1' MINUTE) AS `window_end`,
    FIRST_VALUE(`trade_price`) AS `open_price`,
    MAX(`trade_price`) AS `high_price`,
    MIN(`trade_price`) AS `low_price`,
    LAST_VALUE(`trade_price`) AS `close_price`,
    SUM(`trade_volume`) AS `volume`,
    COUNT(*) AS `trade_count`,
    SUM(`trade_price` * `trade_volume`) / SUM(`trade_volume`) AS `vwap`,
    DATE_FORMAT(TUMBLE_START(`event_time`, INTERVAL '1' MINUTE), 'yyyy-MM-dd') AS `dt`,
    DATE_FORMAT(TUMBLE_START(`event_time`, INTERVAL '1' MINUTE), 'HH') AS `hh`
FROM default_catalog.default_database.kafka_trade
GROUP BY
    `market`,
    TUMBLE(`event_time`, INTERVAL '1' MINUTE);
