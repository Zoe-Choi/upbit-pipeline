-- Flink SQL Client 초기화 스크립트
-- SQL Client 시작 시 자동 실행

-- ============================================
-- 프로덕션 필수 설정
-- ============================================

-- Checkpointing (장애 복구 필수)
SET 'execution.checkpointing.interval' = '60s';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';
SET 'execution.checkpointing.timeout' = '10min';

-- Incremental Checkpoint (RocksDB)
SET 'state.backend.incremental' = 'true';

-- Restart Strategy (자동 복구)
SET 'restart-strategy.type' = 'exponential-delay';
SET 'restart-strategy.exponential-delay.initial-backoff' = '1s';
SET 'restart-strategy.exponential-delay.max-backoff' = '60s';

-- Parallelism (Kafka 파티션 수에 맞춤)
SET 'parallelism.default' = '3';

-- ============================================
-- Paimon 카탈로그 생성
CREATE CATALOG paimon_catalog WITH (
    'type' = 'paimon',
    'warehouse' = 's3://paimon/warehouse',
    's3.endpoint' = 'http://minio-1:9000',
    's3.access-key' = 'minioadmin',
    's3.secret-key' = 'minioadmin',
    's3.path.style.access' = 'true'
);

-- Kafka 소스 테이블 생성
CREATE TABLE IF NOT EXISTS kafka_ticker (
    `market` STRING,
    `trade_price` DOUBLE,
    `opening_price` DOUBLE,
    `high_price` DOUBLE,
    `low_price` DOUBLE,
    `prev_closing_price` DOUBLE,
    `change` STRING,
    `change_rate` DOUBLE,
    `trade_volume` DOUBLE,
    `acc_trade_volume_24h` DOUBLE,
    `acc_trade_price_24h` DOUBLE,
    `trade_timestamp` BIGINT,
    `timestamp` BIGINT,
    `_ingested_at` STRING,
    `event_time` AS TO_TIMESTAMP_LTZ(`trade_timestamp`, 3),
    WATERMARK FOR `event_time` AS `event_time` - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-ticker',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'properties.group.id' = 'flink-ticker-consumer',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json',
    'json.ignore-parse-errors' = 'true'
);

CREATE TABLE IF NOT EXISTS kafka_trade (
    `market` STRING,
    `trade_price` DOUBLE,
    `trade_volume` DOUBLE,
    `ask_bid` STRING,
    `trade_timestamp` BIGINT,
    `timestamp` BIGINT,
    `sequential_id` BIGINT,
    `_ingested_at` STRING,
    `event_time` AS TO_TIMESTAMP_LTZ(`trade_timestamp`, 3),
    WATERMARK FOR `event_time` AS `event_time` - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-trade',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'properties.group.id' = 'flink-trade-consumer',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json',
    'json.ignore-parse-errors' = 'true'
);
