# 6. 업비트 실시간 데이터 파이프라인 구현

> 이 문서에서는 업비트 WebSocket → Kafka → Flink → Paimon(MinIO) 파이프라인의 구현을 다룹니다.

---

## 목차

1. [아키텍처 개요](#아키텍처-개요)
2. [프로젝트 구조](#프로젝트-구조)
3. [핵심 컴포넌트](#핵심-컴포넌트)
4. [데이터 모델](#데이터-모델)
5. [Flink SQL 스크립트](#flink-sql-스크립트)
6. [실행 방법](#실행-방법)
7. [모니터링](#모니터링)

---

## 아키텍처 개요

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Upbit WebSocket │────▶│  Kafka Cluster  │────▶│  Flink Cluster  │────▶│ Paimon (MinIO)  │
│   (실시간 시세)   │     │  (3 Brokers)    │     │ (1 JM + 2 TM)   │     │  (4 Nodes + LB) │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │                       │
         │                       │                       │                       │
    Python Client           Kafka Topics            Streaming Jobs          Lake Tables
    - ticker               - upbit-ticker          - ticker job            - ticker
    - trade                - upbit-trade           - trade job             - trade
    - orderbook            - upbit-orderbook       - ohlcv 1m agg          - orderbook
                                                                           - ohlcv_1m
```

### 데이터 흐름

1. **Upbit WebSocket** → Python 클라이언트가 실시간 시세 데이터 수신
2. **Kafka Producer** → JSON 직렬화하여 토픽에 메시지 전송
3. **Flink Consumer** → Kafka 토픽에서 스트리밍 데이터 소비
4. **Paimon Writer** → 데이터 레이크 테이블에 저장 (MinIO S3)

---

## 프로젝트 구조

```
upbit-pipeline/
├── src/
│   ├── __init__.py
│   ├── main.py                    # 엔트리 포인트
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py            # 환경변수 기반 설정
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ticker.py              # Ticker 데이터 모델
│   │   ├── trade.py               # Trade 데이터 모델
│   │   └── orderbook.py           # Orderbook 데이터 모델
│   ├── producers/
│   │   ├── __init__.py
│   │   └── kafka_producer.py      # Kafka Producer
│   ├── consumers/
│   │   ├── __init__.py
│   │   └── upbit_websocket.py     # WebSocket 클라이언트
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── kafka_handler.py       # 메시지 핸들러
│   └── utils/
│       ├── __init__.py
│       ├── logging.py             # 로깅 유틸리티
│       └── serialization.py       # 직렬화 유틸리티
├── flink-sql/
│   ├── 01-create-catalogs.sql     # Paimon 카탈로그 생성
│   ├── 02-create-kafka-sources.sql # Kafka 소스 테이블
│   ├── 03-create-paimon-tables.sql # Paimon 싱크 테이블
│   ├── 04-streaming-jobs.sql      # 스트리밍 잡 정의
│   └── 05-queries.sql             # 분석 쿼리
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   └── test_models.py
├── scripts/
│   ├── run-pipeline.sh            # 파이프라인 실행
│   ├── setup-minio-buckets.sh     # MinIO 버킷 생성
│   ├── start-flink-jobs.sh        # Flink 잡 시작
│   └── test-kafka.sh              # Kafka 테스트
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## 핵심 컴포넌트

### 1. 설정 관리 (`src/config/settings.py`)

환경변수 기반의 타입 안전한 설정 관리:

```python
from dataclasses import dataclass, field
from functools import lru_cache
from os import getenv

@dataclass(frozen=True)
class KafkaConfig:
    """Kafka producer configuration."""
    bootstrap_servers: str = field(
        default_factory=lambda: getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:29092,localhost:29093,localhost:29094"
        )
    )
    topic_ticker: str = field(
        default_factory=lambda: getenv("KAFKA_TOPIC_TICKER", "upbit-ticker")
    )
    # ... 기타 설정

@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """싱글톤 패턴으로 설정 인스턴스 반환"""
    return AppConfig()
```

**특징:**
- `dataclass(frozen=True)`: 불변 설정 객체
- `field(default_factory=...)`: 지연 평가로 환경변수 로드
- `@lru_cache`: 싱글톤 패턴 구현

### 2. 데이터 모델 (`src/models/`)

업비트 WebSocket API 응답을 타입 안전하게 파싱:

```python
@dataclass
class TickerMessage:
    """Upbit Ticker WebSocket message."""
    market: str
    trade_price: float
    opening_price: float
    # ... 필드들

    @classmethod
    def from_websocket(cls, data: Dict[str, Any]) -> "TickerMessage":
        """WebSocket 응답을 객체로 변환"""
        return cls(
            market=data["market"],
            trade_price=float(data["trade_price"]),
            # ...
        )

    def to_kafka_message(self) -> Dict[str, Any]:
        """Kafka 메시지 형식으로 변환 (메타데이터 추가)"""
        data = self.to_dict()
        data["_ingested_at"] = datetime.utcnow().isoformat()
        data["_source"] = "upbit_websocket"
        return data
```

### 3. WebSocket 클라이언트 (`src/consumers/upbit_websocket.py`)

자동 재연결과 하트비트를 지원하는 WebSocket 클라이언트:

```python
class UpbitWebSocketClient:
    """
    Features:
    - 자동 재연결 (지수 백오프)
    - PING/PONG 하트비트
    - 다중 구독 지원
    - 그레이스풀 셧다운
    """

    async def _reconnect_with_backoff(self) -> bool:
        """지수 백오프로 재연결 시도"""
        delay = min(
            self._config.reconnect_delay * (2 ** (self._reconnect_count - 1)),
            60  # 최대 60초
        )
        await asyncio.sleep(delay)
        # ...
```

### 4. Kafka Producer (`src/producers/kafka_producer.py`)

스레드 안전한 Kafka Producer:

```python
class UpbitKafkaProducer:
    """
    Features:
    - 싱글톤 패턴 (스레드 안전)
    - 전달 확인 콜백
    - 그레이스풀 셧다운
    """

    _instance: Optional["UpbitKafkaProducer"] = None
    _lock: Lock = Lock()

    def __new__(cls, config=None) -> "UpbitKafkaProducer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Double-checked locking
                    instance = super().__new__(cls)
                    cls._instance = instance
        return cls._instance
```

---

## 데이터 모델

### Ticker (현재가)

| 필드 | 타입 | 설명 |
|------|------|------|
| market | STRING | 마켓 코드 (예: KRW-BTC) |
| trade_price | DOUBLE | 현재가 |
| opening_price | DOUBLE | 시가 |
| high_price | DOUBLE | 고가 |
| low_price | DOUBLE | 저가 |
| change | STRING | 전일 대비 (RISE/EVEN/FALL) |
| change_rate | DOUBLE | 전일 대비 등락률 |
| acc_trade_volume_24h | DOUBLE | 24시간 누적 거래량 |
| trade_timestamp | BIGINT | 체결 타임스탬프 (ms) |

### Trade (체결)

| 필드 | 타입 | 설명 |
|------|------|------|
| market | STRING | 마켓 코드 |
| trade_price | DOUBLE | 체결가 |
| trade_volume | DOUBLE | 체결량 |
| ask_bid | STRING | 매수/매도 (ASK/BID) |
| sequential_id | BIGINT | 체결 순서 ID |
| trade_timestamp | BIGINT | 체결 타임스탬프 (ms) |

### Orderbook (호가)

| 필드 | 타입 | 설명 |
|------|------|------|
| market | STRING | 마켓 코드 |
| total_ask_size | DOUBLE | 총 매도 잔량 |
| total_bid_size | DOUBLE | 총 매수 잔량 |
| best_ask_price | DOUBLE | 최우선 매도호가 |
| best_bid_price | DOUBLE | 최우선 매수호가 |
| spread | DOUBLE | 스프레드 (매도-매수) |

---

## Flink SQL 스크립트

### 1. Paimon 카탈로그 생성

```sql
CREATE CATALOG paimon_catalog WITH (
    'type' = 'paimon',
    'warehouse' = 's3://paimon/warehouse',
    's3.endpoint' = 'http://minio-lb:9000',
    's3.access-key' = 'minioadmin',
    's3.secret-key' = 'minioadmin',
    's3.path.style.access' = 'true'
);
```

### 2. Kafka 소스 테이블

```sql
CREATE TABLE kafka_ticker (
    `market` STRING,
    `trade_price` DOUBLE,
    -- ... 필드들
    `event_time` AS TO_TIMESTAMP_LTZ(`trade_timestamp`, 3),
    WATERMARK FOR `event_time` AS `event_time` - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-ticker',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'format' = 'json'
);
```

### 3. Paimon 싱크 테이블 (파티션 + Deduplicate)

```sql
CREATE TABLE ticker (
    -- 필드들...
    `dt` STRING,  -- 파티션 키
    PRIMARY KEY (`market`, `dt`) NOT ENFORCED
) PARTITIONED BY (`dt`)
WITH (
    'merge-engine' = 'deduplicate',
    'changelog-producer' = 'input',
    'snapshot.time-retained' = '1 h'
);
```

### 4. 1분봉 집계 (OHLCV)

```sql
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
    SUM(`trade_price` * `trade_volume`) / SUM(`trade_volume`) AS `vwap`
FROM kafka_trade
GROUP BY `market`, TUMBLE(`event_time`, INTERVAL '1' MINUTE);
```

---

## 실행 방법

### 1. 환경 준비

```bash
# 환경 변수 설정
cp .env.example .env
# .env 파일 수정 (필요시)

# 인프라 시작
docker compose up -d

# MinIO 버킷 생성
./scripts/setup-minio-buckets.sh
```

### 2. Python 파이프라인 실행

```bash
# 가상환경 생성 및 의존성 설치
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev,storage]"

# 파이프라인 실행
python -m src.main

# 또는 스크립트 사용
./scripts/run-pipeline.sh
```

### 3. Flink 스트리밍 잡 시작

```bash
# Flink SQL Client 접속
docker exec -it flink-jobmanager /opt/flink/bin/sql-client.sh

# SQL 파일 실행 (순서대로)
Flink SQL> SOURCE '/opt/flink/flink-sql/01-create-catalogs.sql';
Flink SQL> SOURCE '/opt/flink/flink-sql/02-create-kafka-sources.sql';
Flink SQL> SOURCE '/opt/flink/flink-sql/03-create-paimon-tables.sql';
Flink SQL> SOURCE '/opt/flink/flink-sql/04-streaming-jobs.sql';
```

### 4. 데이터 확인

```bash
# Kafka 메시지 확인
docker exec -it kafka-1 /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server kafka-1:9092 \
    --topic upbit-ticker \
    --from-beginning \
    --max-messages 5
```

```sql
-- Flink SQL에서 Paimon 테이블 조회
USE CATALOG paimon_catalog;
USE upbit;

SELECT * FROM ticker WHERE market = 'KRW-BTC' LIMIT 10;
SELECT * FROM ohlcv_1m ORDER BY window_start DESC LIMIT 10;
```

---

## 모니터링

### UI 대시보드

| 서비스 | URL | 용도 |
|--------|-----|------|
| Kafka UI | http://localhost:8080 | 토픽/메시지 모니터링 |
| Flink UI | http://localhost:8081 | 잡 상태/메트릭 |
| MinIO Console | http://localhost:9001 | 스토리지 모니터링 |

### 파이프라인 통계

```python
# 핸들러 통계 확인
handler = KafkaMessageHandler()
print(handler.stats)
# {
#     "ticker_count": 15000,
#     "trade_count": 45000,
#     "orderbook_count": 5000,
#     "producer_stats": {"delivered": 65000, "errors": 0}
# }
```

### Flink 잡 모니터링

```sql
-- 실행 중인 잡 확인
SHOW JOBS;

-- 잡 취소
STOP JOB '<job_id>' WITH SAVEPOINT;
```

---

## 다음 단계

- [ ] Prometheus + Grafana 모니터링 대시보드
- [ ] Kafka → ClickHouse 실시간 적재
- [ ] ML 모델 학습을 위한 피처 스토어
- [ ] Kubernetes 배포 (Helm Charts)
