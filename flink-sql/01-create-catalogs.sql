-- ============================================================
-- Flink SQL: Catalog Configuration
-- Creates Paimon catalog connected to MinIO S3
-- ============================================================
-- 
-- 사전 준비: JAR 파일 다운로드 필요
-- 아래 명령어를 먼저 실행하세요:
--
-- docker exec flink-jobmanager bash -c "
--   cd /opt/flink/lib && 
--   wget -q https://repo1.maven.org/maven2/org/apache/paimon/paimon-flink-1.18/0.7.0-incubating/paimon-flink-1.18-0.7.0-incubating.jar &&
--   wget -q https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar &&
--   wget -q https://repo1.maven.org/maven2/org/apache/paimon/paimon-s3/0.7.0-incubating/paimon-s3-0.7.0-incubating.jar
-- "
-- docker compose restart flink-jobmanager flink-taskmanager-1 flink-taskmanager-2
--
-- ============================================================

-- Create Paimon Catalog with MinIO S3 backend
CREATE CATALOG paimon_catalog WITH (
    'type' = 'paimon',
    'warehouse' = 's3://paimon/warehouse',
    's3.endpoint' = 'http://minio-1:9000',
    's3.access-key' = 'minioadmin',
    's3.secret-key' = 'minioadmin',
    's3.path.style.access' = 'true'
);
