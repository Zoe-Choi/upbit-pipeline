-- ============================================
-- ClickHouse 분산 테이블 초기화 스크립트
-- ============================================
-- 
-- Kafka → ClickHouse 실시간 연동
-- 7일 TTL 자동 삭제
-- 2샤드 분산 클러스터
--
-- 실행 방법: 
--   docker exec -i clickhouse-1 clickhouse-client < clickhouse/init.sql

-- ============================================
-- 1. 데이터베이스 생성
-- ============================================
CREATE DATABASE IF NOT EXISTS upbit ON CLUSTER upbit_cluster;

-- ============================================
-- 2. Ticker 로컬 테이블 (각 샤드에 실제 데이터 저장)
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.ticker_local ON CLUSTER upbit_cluster
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
TTL trade_date + INTERVAL 7 DAY DELETE  -- 7일 후 자동 삭제
SETTINGS index_granularity = 8192;

-- ============================================
-- 3. Ticker 분산 테이블 (2샤드를 하나로 묶음)
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.ticker ON CLUSTER upbit_cluster
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
    event_time DateTime64(3),
    trade_date Date
)
ENGINE = Distributed(
    'upbit_cluster',
    'upbit',
    'ticker_local',
    xxHash64(market)
);

-- ============================================
-- 4. Trade 로컬 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.trade_local ON CLUSTER upbit_cluster
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

-- Trade 분산 테이블
CREATE TABLE IF NOT EXISTS upbit.trade ON CLUSTER upbit_cluster
(
    market String,
    trade_price Float64,
    trade_volume Float64,
    ask_bid String,
    trade_timestamp Int64,
    `timestamp` Int64,
    sequential_id Int64,
    ingested_at String,
    event_time DateTime64(3),
    trade_date Date
)
ENGINE = Distributed('upbit_cluster', 'upbit', 'trade_local', xxHash64(market));

-- ============================================
-- 5. Kafka 연동 테이블 (Ticker)
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.ticker_kafka ON CLUSTER upbit_cluster
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

-- Kafka → 로컬 테이블 자동 적재 (Materialized View)
CREATE MATERIALIZED VIEW IF NOT EXISTS upbit.ticker_kafka_mv ON CLUSTER upbit_cluster
TO upbit.ticker_local AS
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
-- 6. Kafka 연동 테이블 (Trade)
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.trade_kafka ON CLUSTER upbit_cluster
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

-- Kafka → 로컬 테이블 자동 적재
CREATE MATERIALIZED VIEW IF NOT EXISTS upbit.trade_kafka_mv ON CLUSTER upbit_cluster
TO upbit.trade_local AS
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
-- 7. 1분 OHLCV 집계 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS upbit.ohlcv_1m_local ON CLUSTER upbit_cluster
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

-- 분산 집계 테이블
CREATE TABLE IF NOT EXISTS upbit.ohlcv_1m ON CLUSTER upbit_cluster
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
ENGINE = Distributed('upbit_cluster', 'upbit', 'ohlcv_1m_local', xxHash64(market));

-- 1분 OHLCV 자동 집계 (Ticker 데이터 기반)
CREATE MATERIALIZED VIEW IF NOT EXISTS upbit.ohlcv_1m_mv ON CLUSTER upbit_cluster
TO upbit.ohlcv_1m_local AS
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
FROM upbit.ticker_local
GROUP BY market, minute;

-- ============================================
-- 8. 알림용 뷰 (급등/급락 감지)
-- ============================================
CREATE VIEW IF NOT EXISTS upbit.price_alerts ON CLUSTER upbit_cluster AS
SELECT 
    market,
    trade_price,
    change_rate,
    event_time,
    CASE 
        WHEN change_rate >= 0.05 THEN 'SURGE'   -- 5% 이상 급등
        WHEN change_rate <= -0.05 THEN 'CRASH'  -- 5% 이상 급락
        ELSE 'NORMAL'
    END AS alert_type
FROM upbit.ticker
WHERE abs(change_rate) >= 0.05
ORDER BY event_time DESC
LIMIT 100;

-- ============================================
-- 9. 확인 쿼리
-- ============================================
-- 클러스터 정보 확인
SELECT * FROM system.clusters WHERE cluster = 'upbit_cluster';

-- 테이블 목록 확인
SHOW TABLES FROM upbit;

-- 데이터 확인 (Kafka 연동 후)
-- SELECT * FROM upbit.ticker ORDER BY event_time DESC LIMIT 10;
