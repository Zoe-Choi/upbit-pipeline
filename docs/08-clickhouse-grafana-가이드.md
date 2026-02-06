# 8. ClickHouse + Grafana 실시간 분석 가이드

## 개요

이 문서는 Kafka 데이터를 ClickHouse로 실시간 적재하고, Grafana로 시각화 및 알림을 설정하는 방법을 설명합니다.

## 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Kafka     │────▶│ ClickHouse  │────▶│   Grafana   │
│  (3 노드)    │     │  (2 샤드)    │     │  (시각화)    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  7일 TTL    │
                    │  자동 삭제   │
                    └─────────────┘
```

## 데이터 흐름

1. **Kafka** → `upbit-ticker`, `upbit-trade` 토픽
2. **ClickHouse Kafka Engine** → 토픽에서 실시간 소비
3. **Materialized View** → 로컬 테이블에 자동 적재
4. **Distributed Table** → 2샤드를 하나의 뷰로 통합
5. **Grafana** → ClickHouse 쿼리로 시각화

## 설정 방법

### 1. 서비스 시작

```bash
# 전체 서비스 시작
docker compose up -d

# 또는 ClickHouse + Grafana만 시작
docker compose up -d clickhouse-keeper clickhouse-1 clickhouse-2 grafana
```

### 2. ClickHouse 테이블 초기화

```bash
# 초기화 스크립트 실행
docker exec -i clickhouse-1 clickhouse-client < clickhouse/init.sql

# 또는 설정 스크립트 사용
./scripts/setup-clickhouse-grafana.sh
```

### 3. 데이터 확인

```bash
# ClickHouse CLI 접속
docker exec -it clickhouse-1 clickhouse-client

# 데이터 확인
SELECT * FROM upbit.ticker ORDER BY event_time DESC LIMIT 10;
SELECT count() FROM upbit.ticker;
```

## ClickHouse 테이블 구조

### 주요 테이블

| 테이블 | 엔진 | 용도 |
|--------|------|------|
| `ticker_kafka` | Kafka | Kafka 토픽 소비 |
| `ticker_local` | MergeTree | 로컬 데이터 저장 |
| `ticker` | Distributed | 분산 쿼리 (2샤드 통합) |
| `ohlcv_1m` | Distributed | 1분 OHLCV 집계 |
| `price_alerts` | View | 급등/급락 알림용 |

### TTL 설정 (7일 자동 삭제)

```sql
-- 테이블 정의에 포함됨
TTL trade_date + INTERVAL 7 DAY DELETE
```

### 클러스터 구성

```
upbit_cluster
├── Shard 1: clickhouse-1 (port 8123)
└── Shard 2: clickhouse-2 (port 8124)
```

## Grafana 접속

- **URL**: http://localhost:3000
- **Username**: admin
- **Password**: admin123

### 기본 대시보드

1. **Upbit Real-time Dashboard**
   - 실시간 가격 차트
   - 변동률 표시
   - 거래량 (1분 단위)
   - 급등/급락 알림 테이블
   - 데이터 현황 통계

### 대시보드 패널 설명

| 패널 | 설명 |
|------|------|
| Real-time Price | 선택한 마켓의 실시간 가격 |
| Change Rate | 마켓별 변동률 (5분 기준) |
| Trade Volume | 1분 OHLCV 거래량 |
| Price Alerts | 5% 이상 급등/급락 이벤트 |
| Total Tickers | 최근 1시간 ticker 수 |
| Data Freshness | 데이터 지연 시간 (초) |

## 알림 설정

### Grafana UI에서 알림 규칙 생성

1. **Alerting** → **Alert rules** → **New alert rule**
2. **Rule name**: Price Surge Alert
3. **Query**:
   ```sql
   SELECT count() as surge_count
   FROM upbit.price_alerts
   WHERE event_time >= now() - INTERVAL 5 MINUTE
     AND alert_type = 'SURGE'
   ```
4. **Condition**: surge_count > 0
5. **Evaluate every**: 1m
6. **Contact point**: 이메일, Slack, Discord 등 설정

### 알림 채널 설정 (예: Slack)

1. **Alerting** → **Contact points** → **Add contact point**
2. **Integration**: Slack
3. **Webhook URL**: Slack Incoming Webhook URL 입력

### 알림 유형 예시

| 알림 | 조건 | 설명 |
|------|------|------|
| 급등 알림 | change_rate >= 5% | 5% 이상 상승 |
| 급락 알림 | change_rate <= -5% | 5% 이상 하락 |
| 데이터 지연 | lag > 60초 | 데이터 수집 지연 |
| 볼륨 급증 | volume > 평균 * 3 | 거래량 폭증 |

## 유용한 쿼리

### 실시간 가격 조회

```sql
SELECT 
    market,
    trade_price,
    change_rate,
    event_time
FROM upbit.ticker
WHERE event_time >= now() - INTERVAL 5 MINUTE
ORDER BY event_time DESC
LIMIT 100;
```

### 1분 OHLCV

```sql
SELECT 
    market,
    minute,
    open, high, low, close,
    volume,
    trade_count
FROM upbit.ohlcv_1m
WHERE market = 'KRW-BTC'
  AND minute >= now() - INTERVAL 1 HOUR
ORDER BY minute;
```

### 급등/급락 감지

```sql
SELECT * FROM upbit.price_alerts
WHERE event_time >= now() - INTERVAL 1 HOUR
ORDER BY event_time DESC;
```

### 마켓별 통계

```sql
SELECT 
    market,
    count() as ticks,
    avg(trade_price) as avg_price,
    max(trade_price) as max_price,
    min(trade_price) as min_price,
    sum(trade_volume) as total_volume
FROM upbit.ticker
WHERE event_time >= now() - INTERVAL 1 HOUR
GROUP BY market
ORDER BY total_volume DESC;
```

### 샤드별 데이터 분포

```sql
SELECT 
    hostName() as shard,
    count() as records
FROM upbit.ticker_local
GROUP BY shard;
```

## 문제 해결

### 데이터가 안 들어올 때

```bash
# Kafka 토픽 확인
docker exec kafka-1 /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic upbit-ticker \
    --from-beginning \
    --max-messages 5

# ClickHouse Kafka 엔진 상태 확인
docker exec clickhouse-1 clickhouse-client --query \
    "SELECT * FROM system.kafka_consumers"
```

### Grafana 데이터소스 연결 오류

```bash
# ClickHouse 접속 테스트
curl 'http://localhost:8123/?query=SELECT%201'
```

### TTL 확인

```sql
-- 파티션별 데이터 확인
SELECT 
    partition,
    count() as rows,
    min(event_time) as min_time,
    max(event_time) as max_time
FROM upbit.ticker_local
GROUP BY partition
ORDER BY partition;
```

## 리소스 사용량

| 서비스 | 메모리 |
|--------|--------|
| ClickHouse-1 | 512MB |
| ClickHouse-2 | 512MB |
| ClickHouse Keeper | 256MB |
| Grafana | 256MB |
| **합계** | **~1.5GB** |

## 다음 단계

1. **Trino 연동** - Paimon 데이터 배치 분석
2. **ML 파이프라인** - 가격 예측 모델
3. **Kubernetes 배포** - 프로덕션 환경
