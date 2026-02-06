# Upbit Pipeline

업비트 API/WebSocket 데이터를 수집하고 처리하는 MLOps 파이프라인 플랫폼

## 시스템 요구사항

- **macOS**: Apple Silicon (M1/M2/M3) 지원
- **RAM**: 최소 16GB
- **Docker Desktop**: 4.0 이상 (Apple Silicon 네이티브)
- **Kubernetes** (선택): Minikube, Kind, 또는 Docker Desktop K8s

## 아키텍처 개요

```
┌─────────────────┐     ┌─────────────────────────────────────┐
│   Upbit API     │────▶│      Kafka Cluster (KRaft 모드)     │
│   WebSocket     │     │  ┌─────────┬─────────┬─────────┐    │
└─────────────────┘     │  │ Broker1 │ Broker2 │ Broker3 │    │
                        │  │  +Ctrl  │  +Ctrl  │  +Ctrl  │    │
                        │  └─────────┴─────────┴─────────┘    │
                        └─────────────────────────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────────────────┐
                        │     Flink Cluster (분산 처리)        │
                        │  ┌─────────────────────────────┐    │
                        │  │      JobManager (1)         │    │
                        │  └─────────────────────────────┘    │
                        │  ┌────────────┐ ┌────────────┐      │
                        │  │TaskManager1│ │TaskManager2│      │
                        │  │  2 slots   │ │  2 slots   │      │
                        │  └────────────┘ └────────────┘      │
                        └─────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
    ┌───────────────────────────┐     ┌───────────────────────────┐
    │  MinIO (S3) + Paimon      │     │  ClickHouse Cluster       │
    │  Data Lake (장기 저장)     │     │  분석 DB (빠른 쿼리)       │
    │                           │     │  ┌───────┐ ┌───────┐      │
    │  • 원본 데이터 보관        │     │  │Shard1 │ │Shard2 │      │
    │  • ML 학습 데이터          │     │  └───────┘ └───────┘      │
    │  • Time Travel            │     │  실시간 대시보드용         │
    └───────────────────────────┘     └───────────────────────────┘
```

> **KRaft 모드**: Zookeeper 없이 Kafka 자체에서 메타데이터 관리 (리소스 절약)
> **Paimon**: Flink와 최적화된 Streaming Data Lake 테이블 포맷
> **ClickHouse**: 초고속 OLAP 데이터베이스 (2샤드 분산 구성)

## 빠른 시작

### 1. Docker Compose (개발 환경 - 권장)

```bash
# 스크립트 실행 권한 부여
chmod +x scripts/*.sh

# 전체 클러스터 시작 (Kafka + Flink + MinIO + ClickHouse)
./scripts/start-docker.sh

# 또는 직접 실행
docker compose up -d

# 클러스터 테스트
./scripts/test-kafka.sh
./scripts/test-clickhouse.sh

# 클러스터 중지
./scripts/stop-docker.sh
```

### 2. Kubernetes (프로덕션/학습 환경)

```bash
# Minikube 시작 (M1 최적화)
minikube start --memory 8192 --cpus 4 --driver=docker

# 또는 Kind 사용
kind create cluster --name upbit-pipeline

# Kafka 클러스터 배포
./scripts/start-k8s.sh

# 클러스터 삭제
./scripts/stop-k8s.sh
```

## 접속 정보

### Docker Compose

| 서비스 | 주소 | 설명 |
|--------|------|------|
| Kafka Broker 1 | `localhost:29092` | 외부 접속용 |
| Kafka Broker 2 | `localhost:29093` | 외부 접속용 |
| Kafka Broker 3 | `localhost:29094` | 외부 접속용 |
| Kafka UI | http://localhost:8080 | Kafka 모니터링 |
| Flink UI | http://localhost:8081 | Flink 대시보드 |
| MinIO Console | http://localhost:9001 | 스토리지 관리 |
| MinIO S3 API | http://localhost:9000 | S3 호환 API |
| ClickHouse 1 | http://localhost:8123 | HTTP API (Shard 1) |
| ClickHouse 2 | http://localhost:8124 | HTTP API (Shard 2) |

### MinIO 접속 정보

```
Access Key: minioadmin
Secret Key: minioadmin
```

### ClickHouse 접속

```bash
# CLI 접속
docker exec -it clickhouse-1 clickhouse-client

# HTTP API
curl 'http://localhost:8123/?query=SELECT%201'

# Python
pip install clickhouse-connect
```

```python
import clickhouse_connect

client = clickhouse_connect.get_client(host='localhost', port=8123)
result = client.query('SELECT * FROM upbit.ticker LIMIT 10')
print(result.result_rows)
```

### 기본 생성 버킷

| 버킷 | 용도 |
|------|------|
| `paimon` | Paimon 테이블 저장소 |
| `checkpoints` | Flink 체크포인트 |
| `warehouse` | 데이터 웨어하우스 |

## 리소스 사용량 (M1 Pro 16GB 기준)

| 구성 요소 | 메모리 | 역할 |
|-----------|--------|------|
| Kafka Broker (x3) | 512MB x 3 | 메시지 스트리밍 |
| Flink JobManager | 768MB | 작업 조율/스케줄링 |
| Flink TaskManager (x2) | 1.3GB x 2 | 작업 실행 (각 2 slots) |
| MinIO | 512MB | S3 호환 스토리지 |
| ClickHouse (x2) | 512MB x 2 | 분석 DB (2샤드) |
| ClickHouse Keeper | 256MB | 분산 조정 |
| Kafka UI | 512MB | Kafka 모니터링 |
| **총합** | **~7.1GB** | |

> 나머지 ~9GB는 ML 학습, Redis 캐시, 기타 서비스에 활용 가능

## 프로젝트 구조

```
upbit-pipeline/
├── src/                              # Python 파이프라인 소스
│   ├── main.py                       # 엔트리 포인트
│   ├── config/                       # 설정 관리
│   │   └── settings.py               # 환경변수 기반 설정
│   ├── models/                       # 데이터 모델
│   │   ├── ticker.py                 # Ticker 모델
│   │   ├── trade.py                  # Trade 모델
│   │   └── orderbook.py              # Orderbook 모델
│   ├── producers/                    # Kafka Producer
│   │   └── kafka_producer.py
│   ├── consumers/                    # WebSocket 클라이언트
│   │   └── upbit_websocket.py
│   ├── pipeline/                     # 파이프라인 핸들러
│   │   └── kafka_handler.py
│   └── utils/                        # 유틸리티
│       ├── logging.py
│       └── serialization.py
├── flink-sql/                        # Flink SQL 스크립트
│   ├── 01-create-catalogs.sql        # Paimon 카탈로그
│   ├── 02-create-kafka-sources.sql   # Kafka 소스 테이블
│   ├── 03-create-paimon-tables.sql   # Paimon 싱크 테이블
│   ├── 04-streaming-jobs.sql         # 스트리밍 잡
│   └── 05-queries.sql                # 분석 쿼리
├── tests/                            # 테스트
│   ├── conftest.py
│   ├── test_config.py
│   └── test_models.py
├── docker-compose.yml                # 전체 클러스터
├── clickhouse/
│   ├── config/
│   │   ├── clickhouse-1-config.xml
│   │   ├── clickhouse-2-config.xml
│   │   ├── users.xml
│   │   └── keeper-config.xml
│   └── init.sql
├── kubernetes/
│   ├── namespace.yaml
│   ├── kafka.yaml
│   └── kafka-ui.yaml
├── scripts/
│   ├── run-pipeline.sh               # 파이프라인 실행
│   ├── setup-minio-buckets.sh        # MinIO 버킷 생성
│   ├── start-flink-jobs.sh           # Flink 잡 시작
│   ├── test-kafka.sh
│   ├── test-clickhouse.sh
│   ├── start-docker.sh
│   ├── stop-docker.sh
│   ├── start-k8s.sh
│   └── stop-k8s.sh
├── docs/                             # 블로그/노션 문서
│   ├── 00-접속정보.md
│   ├── 01-프로젝트-개요.md
│   ├── 02-kafka-클러스터-구축.md
│   ├── 03-flink-클러스터-구축.md
│   ├── 04-minio-paimon-스토리지.md
│   ├── 05-cursor-mcp-설정.md
│   └── 06-upbit-pipeline-구현.md
├── requirements.txt
├── pyproject.toml
├── .env.example
└── .env                              # 로컬 환경변수 (gitignore)
```

## 클러스터 설정

### Kafka

| 설정 | 값 | 설명 |
|------|-----|------|
| `num.partitions` | 3 | 기본 파티션 수 |
| `default.replication.factor` | 3 | 복제 계수 |
| `min.insync.replicas` | 2 | 최소 동기화 복제본 |
| `auto.create.topics.enable` | true | 자동 토픽 생성 |

### Flink

| 설정 | 값 | 설명 |
|------|-----|------|
| TaskManager 수 | 2 | 분산 처리 노드 |
| Slots per TM | 2 | TM당 병렬 슬롯 |
| 총 병렬도 | 4 | 동시 처리 가능 태스크 |
| State Backend | RocksDB | 상태 저장소 |
| Checkpoint Storage | MinIO (S3) | 체크포인트 저장 |

### ClickHouse

| 설정 | 값 | 설명 |
|------|-----|------|
| 클러스터 이름 | upbit_cluster | 분산 쿼리용 |
| 샤드 수 | 2 | 데이터 수평 분할 |
| Keeper | 1 노드 | 분산 조정 (ZK 대체) |
| 샤딩 키 | xxHash64(symbol) | 심볼별 분산 |

## Python 연동 예시

### Kafka Producer/Consumer

```python
from kafka import KafkaProducer, KafkaConsumer
import json

# Producer
producer = KafkaProducer(
    bootstrap_servers=['localhost:29092', 'localhost:29093', 'localhost:29094'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# 메시지 전송
producer.send('upbit-ticker', {'symbol': 'BTC', 'price': 50000000})
producer.flush()

# Consumer
consumer = KafkaConsumer(
    'upbit-ticker',
    bootstrap_servers=['localhost:29092', 'localhost:29093', 'localhost:29094'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    group_id='my-group'
)

for message in consumer:
    print(f"Received: {message.value}")
```

### ClickHouse 쿼리

```python
import clickhouse_connect

# 연결
client = clickhouse_connect.get_client(host='localhost', port=8123)

# 분산 테이블에 데이터 삽입
client.insert('upbit.ticker', 
    [['BTC', 50000000, 1.5, 0.02, '2024-01-01 10:00:00']],
    column_names=['symbol', 'price', 'volume', 'change_rate', 'trade_time']
)

# 집계 쿼리 (2샤드에서 병렬 처리)
result = client.query('''
    SELECT 
        symbol,
        avg(price) as avg_price,
        max(price) as max_price,
        count() as cnt
    FROM upbit.ticker
    GROUP BY symbol
''')

for row in result.result_rows:
    print(row)
```

### MinIO (S3) 접근

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin'
)

# 버킷 목록
print(s3.list_buckets())

# 파일 업로드
s3.upload_file('data.parquet', 'warehouse', 'raw/data.parquet')
```

## 문제 해결

### Docker 메모리 부족

Docker Desktop > Settings > Resources에서 메모리를 8GB 이상으로 설정

### Kafka 브로커 연결 실패

```bash
# 컨테이너 상태 확인
docker compose ps

# 로그 확인
docker compose logs kafka-1
```

### ClickHouse 연결 실패

```bash
# 상태 확인
docker compose ps clickhouse-1 clickhouse-2 clickhouse-keeper

# 로그 확인
docker compose logs clickhouse-1

# Keeper 연결 확인
docker exec clickhouse-1 clickhouse-client --query "SELECT * FROM system.zookeeper WHERE path = '/'"
```

### Flink JobManager 연결 실패

```bash
# Flink 로그 확인
docker compose logs flink-jobmanager

# TaskManager 상태 확인
docker compose logs flink-taskmanager-1
```

### MinIO 버킷 생성 실패

```bash
# MinIO 초기화 다시 실행
docker compose restart minio-init

# 수동 버킷 생성
docker exec minio mc mb local/paimon
```

## 업비트 파이프라인 실행

### 1. 인프라 시작

```bash
# 환경 변수 설정
cp .env.example .env
# .env 파일 수정

# 전체 클러스터 시작
docker compose up -d

# MinIO 버킷 생성
./scripts/setup-minio-buckets.sh
```

### 2. Python 파이프라인 실행 (WebSocket → Kafka)

```bash
# 가상환경 생성 및 의존성 설치
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev,storage]"

# 파이프라인 실행
python -m src.main
```

### 3. Flink 스트리밍 잡 시작 (Kafka → Paimon)

```bash
# Flink SQL Client 접속
docker exec -it flink-jobmanager /opt/flink/bin/sql-client.sh

# SQL 파일 순서대로 실행
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
    --max-messages 5
```

## 다음 단계

- [x] Kafka 클러스터 (3 brokers, KRaft 모드)
- [x] Flink 클러스터 (1 JM + 2 TM)
- [x] MinIO 스토리지 (Paimon 저장소)
- [x] ClickHouse 클러스터 (2샤드 분산)
- [x] Apache Paimon 카탈로그 설정
- [x] 업비트 WebSocket 데이터 수집기 구현
- [x] Flink SQL로 실시간 분석 쿼리
- [ ] Kafka → ClickHouse 실시간 적재
- [ ] ML 모델 학습 파이프라인 구축
- [ ] Prometheus + Grafana 모니터링

## 라이선스

MIT License
