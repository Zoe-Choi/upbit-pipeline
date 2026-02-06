#!/bin/bash
# ============================================
# ClickHouse + Grafana 설정 스크립트
# ============================================

set -e

echo "============================================"
echo "ClickHouse + Grafana Setup"
echo "============================================"

# 1. ClickHouse 상태 확인
echo ""
echo "[1/4] Checking ClickHouse status..."
if ! docker exec clickhouse-1 clickhouse-client --query "SELECT 1" > /dev/null 2>&1; then
    echo "ERROR: ClickHouse is not running!"
    echo "Please run: docker compose up -d clickhouse-keeper clickhouse-1 clickhouse-2"
    exit 1
fi
echo "ClickHouse is running."

# 2. ClickHouse 테이블 초기화
echo ""
echo "[2/4] Initializing ClickHouse tables..."
docker exec -i clickhouse-1 clickhouse-client < clickhouse/init.sql 2>/dev/null || {
    echo "Some tables may already exist (this is OK)"
}
echo "ClickHouse tables initialized."

# 3. Grafana 시작
echo ""
echo "[3/4] Starting Grafana..."
docker compose up -d grafana

# Grafana 준비 대기
echo "Waiting for Grafana to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:3000/api/health | grep -q "ok"; then
        break
    fi
    sleep 2
done

# 4. 상태 확인
echo ""
echo "[4/4] Verifying setup..."
echo ""

# ClickHouse 테이블 확인
echo "ClickHouse Tables:"
docker exec clickhouse-1 clickhouse-client --query "SHOW TABLES FROM upbit" 2>/dev/null || echo "  (waiting for tables)"
echo ""

# Kafka 토픽에서 데이터 흐름 확인
echo "Checking Kafka data flow..."
TICKER_COUNT=$(docker exec clickhouse-1 clickhouse-client --query "SELECT count() FROM upbit.ticker_local" 2>/dev/null || echo "0")
echo "  Ticker records: $TICKER_COUNT"

TRADE_COUNT=$(docker exec clickhouse-1 clickhouse-client --query "SELECT count() FROM upbit.trade_local" 2>/dev/null || echo "0")
echo "  Trade records: $TRADE_COUNT"

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Access URLs:"
echo "  - Grafana:     http://localhost:3000 (admin/admin123)"
echo "  - ClickHouse:  http://localhost:8123 (HTTP)"
echo "  - Kafka UI:    http://localhost:8080"
echo "  - Flink UI:    http://localhost:8081"
echo ""
echo "ClickHouse CLI:"
echo "  docker exec -it clickhouse-1 clickhouse-client"
echo ""
echo "Sample Queries:"
echo "  SELECT * FROM upbit.ticker ORDER BY event_time DESC LIMIT 10;"
echo "  SELECT * FROM upbit.price_alerts LIMIT 10;"
echo "  SELECT * FROM upbit.ohlcv_1m ORDER BY minute DESC LIMIT 10;"
echo ""
echo "Data Retention: 7 days (TTL auto-delete)"
echo "============================================"
