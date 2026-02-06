-- ============================================
-- ClickHouse 단일 노드 초기화 스크립트
-- ============================================
-- 
-- Kafka → ClickHouse 실시간 연동
-- 7일 TTL 자동 삭제
-- 단일 노드 (M1 16GB 환경 최적화)
--
-- 실행 방법: 
--   docker exec -i clickhouse-1 clickhouse-client < clickhouse/init-simple.sql

-- ============================================
-- 1. 데이터베이스 생성
-- ============================================
CREATE DATABASE IF NOT EXISTS upbit;

-- ============================================
-- 2. Ticker 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.ticker
(
    market String,
    trade_price Float64,
    opening_price Float64,
    high_price Float64,
    low_price Float64,
    prev_closing_price Float64,
    change String,
    change_rate Float64,
    trade_volume Float64,
    acc_trade_volume_24h Float64,
    acc_trade_price_24h Float64,
    trade_timestamp Int64,
    `timestamp` Int64,
    ingested_at String,
    
    -- 파생 컬럼
    event_time DateTime64(3) DEFAULT fromUnixTimestamp64Milli(trade_timestamp),
    trade_date Date DEFAULT toDate(event_time)
)
ENGINE = MergeTree()
PARTITION BY trade_date
ORDER BY (market, event_time)
TTL trade_date + INTERVAL 7 DAY DELETE
SETTINGS index_granularity = 8192;

-- ============================================
-- 3. Trade 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.trade
(
    market String,
    trade_price Float64,
    trade_volume Float64,
    ask_bid String,
    trade_timestamp Int64,
    `timestamp` Int64,
    sequential_id Int64,
    ingested_at String,
    
    event_time DateTime64(3) DEFAULT fromUnixTimestamp64Milli(trade_timestamp),
    trade_date Date DEFAULT toDate(event_time)
)
ENGINE = MergeTree()
PARTITION BY trade_date
ORDER BY (market, event_time, sequential_id)
TTL trade_date + INTERVAL 7 DAY DELETE
SETTINGS index_granularity = 8192;

-- ============================================
-- 4. Kafka 연동 테이블 (Ticker)
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.ticker_kafka
(
    market String,
    trade_price Float64,
    opening_price Float64,
    high_price Float64,
    low_price Float64,
    prev_closing_price Float64,
    change String,
    change_rate Float64,
    trade_volume Float64,
    acc_trade_volume_24h Float64,
    acc_trade_price_24h Float64,
    trade_timestamp Int64,
    `timestamp` Int64,
    `_ingested_at` String
)
ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    kafka_topic_list = 'upbit-ticker',
    kafka_group_name = 'clickhouse-ticker-consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 2,
    kafka_max_block_size = 1048576;

-- Kafka → ticker 테이블 자동 적재
CREATE MATERIALIZED VIEW IF NOT EXISTS upbit.ticker_kafka_mv
TO upbit.ticker AS
SELECT 
    market,
    trade_price,
    opening_price,
    high_price,
    low_price,
    prev_closing_price,
    change,
    change_rate,
    trade_volume,
    acc_trade_volume_24h,
    acc_trade_price_24h,
    trade_timestamp,
    `timestamp`,
    `_ingested_at` AS ingested_at,
    fromUnixTimestamp64Milli(trade_timestamp) AS event_time,
    toDate(fromUnixTimestamp64Milli(trade_timestamp)) AS trade_date
FROM upbit.ticker_kafka;

-- ============================================
-- 5. Kafka 연동 테이블 (Trade)
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.trade_kafka
(
    market String,
    trade_price Float64,
    trade_volume Float64,
    ask_bid String,
    trade_timestamp Int64,
    `timestamp` Int64,
    sequential_id Int64,
    `_ingested_at` String
)
ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    kafka_topic_list = 'upbit-trade',
    kafka_group_name = 'clickhouse-trade-consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 2,
    kafka_max_block_size = 1048576;

-- Kafka → trade 테이블 자동 적재
CREATE MATERIALIZED VIEW IF NOT EXISTS upbit.trade_kafka_mv
TO upbit.trade AS
SELECT 
    market,
    trade_price,
    trade_volume,
    ask_bid,
    trade_timestamp,
    `timestamp`,
    sequential_id,
    `_ingested_at` AS ingested_at,
    fromUnixTimestamp64Milli(trade_timestamp) AS event_time,
    toDate(fromUnixTimestamp64Milli(trade_timestamp)) AS trade_date
FROM upbit.trade_kafka;

-- ============================================
-- 6. 1분 OHLCV 집계 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.ohlcv_1m
(
    market String,
    minute DateTime,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    trade_count UInt64,
    avg_price Float64
)
ENGINE = ReplacingMergeTree()
PARTITION BY toDate(minute)
ORDER BY (market, minute)
TTL toDate(minute) + INTERVAL 7 DAY DELETE;

-- 1분 OHLCV 자동 집계
CREATE MATERIALIZED VIEW IF NOT EXISTS upbit.ohlcv_1m_mv
TO upbit.ohlcv_1m AS
SELECT 
    market,
    toStartOfMinute(event_time) AS minute,
    argMin(trade_price, event_time) AS open,
    max(trade_price) AS high,
    min(trade_price) AS low,
    argMax(trade_price, event_time) AS close,
    sum(trade_volume) AS volume,
    count() AS trade_count,
    avg(trade_price) AS avg_price
FROM upbit.ticker
GROUP BY market, minute;

-- ============================================
-- 7. 알림용 뷰 (급등/급락 감지)
-- ============================================
CREATE VIEW IF NOT EXISTS upbit.price_alerts AS
SELECT 
    market,
    trade_price,
    change_rate,
    event_time,
    CASE 
        WHEN change_rate >= 0.05 THEN 'SURGE'
        WHEN change_rate <= -0.05 THEN 'CRASH'
        ELSE 'NORMAL'
    END AS alert_type
FROM upbit.ticker
WHERE abs(change_rate) >= 0.05
ORDER BY event_time DESC
LIMIT 100;

-- ============================================
-- 8. 확인
-- ============================================
SHOW TABLES FROM upbit;
