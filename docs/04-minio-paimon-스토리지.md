# M1 맥북에서 MinIO + Apache Paimon 데이터 레이크 구축하기

> S3 호환 스토리지 MinIO와 스트리밍 데이터 레이크 Paimon을 설정합니다.

## 시리즈 목차

1. [프로젝트 개요](./01-프로젝트-개요.md)
2. [Kafka 클러스터 구축 (KRaft 모드)](./02-kafka-클러스터-구축.md)
3. [Flink 클러스터 구축](./03-flink-클러스터-구축.md)
4. **MinIO + Apache Paimon 스토리지** (현재 글)
5. [Cursor MCP 개발 환경 설정](./05-cursor-mcp-설정.md)

---

## 데이터 저장소 전략

### 왜 여러 저장소가 필요한가?

실시간 데이터 파이프라인에서는 데이터 접근 패턴에 따라 다른 저장소를 사용합니다.

```
데이터 흐름과 저장소 계층

┌─────────────────────────────────────────────────────────────┐
│                    Hot (실시간)                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Redis                             │    │
│  │  - 현재 가격, 세션 데이터                            │    │
│  │  - 밀리초 단위 응답                                  │    │
│  │  - 메모리 저장 (휘발성)                              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Warm (최근 데이터)                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               TimescaleDB / Paimon                   │    │
│  │  - 최근 1주일~1개월 데이터                           │    │
│  │  - 분석 쿼리, 대시보드                              │    │
│  │  - 빠른 조회 성능                                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Cold (장기 보관)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              MinIO (S3) / Parquet                    │    │
│  │  - 전체 히스토리 데이터                              │    │
│  │  - ML 학습용 데이터셋                               │    │
│  │  - 저비용 대용량 저장                               │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 저장소별 특징 비교

| 저장소 | 유형 | 지연시간 | 용량 | 비용 | 용도 |
|--------|------|----------|------|------|------|
| **Redis** | In-Memory | ~1ms | GB | 높음 | 캐시, 실시간 |
| **TimescaleDB** | Time-Series DB | ~10ms | TB | 중간 | 시계열 분석 |
| **Paimon** | Data Lake Table | ~100ms | PB | 낮음 | 스트리밍 레이크 |
| **MinIO (S3)** | Object Storage | ~100ms | PB | 매우 낮음 | 원본 데이터 |

---

## MinIO란?

### 개요

**MinIO**는 **S3 호환 오픈소스 객체 스토리지**입니다. AWS S3 API와 100% 호환되어, 로컬 개발 환경에서 S3를 대체할 수 있습니다.

### 왜 MinIO인가?

| AWS S3 | MinIO |
|--------|-------|
| 클라우드 서비스 | 로컬/온프레미스 |
| 종량제 비용 | 무료 (오픈소스) |
| 인터넷 필요 | 로컬 네트워크 |
| 프로덕션 환경 | 개발/테스트 환경 |

> **장점**: S3용으로 작성한 코드를 수정 없이 MinIO에서 테스트 가능

### MinIO 핵심 개념

```
MinIO Server
┌─────────────────────────────────────────┐
│                                         │
│  Bucket: paimon                         │
│  ├── db/                                │
│  │   └── upbit_ticker/                  │
│  │       ├── dt=2024-01-01/            │
│  │       │   └── data-0001.parquet     │
│  │       └── dt=2024-01-02/            │
│  │           └── data-0002.parquet     │
│  │                                      │
│  Bucket: checkpoints                    │
│  ├── job-001/                          │
│  │   └── chk-100/                      │
│  │                                      │
│  Bucket: warehouse                      │
│  └── raw/                              │
│      └── upbit_raw.parquet             │
└─────────────────────────────────────────┘
```

| 용어 | 설명 |
|------|------|
| **Bucket** | 최상위 컨테이너 (S3의 버킷과 동일) |
| **Object** | 저장되는 파일 (Parquet, JSON 등) |
| **Prefix** | 폴더처럼 보이는 경로 (실제론 키의 일부) |

---

## Apache Paimon이란?

### 개요

**Apache Paimon**은 **스트리밍 데이터 레이크 테이블 포맷**입니다. Flink와 긴밀하게 통합되어 실시간 데이터 업데이트, ACID 트랜잭션, Time Travel을 지원합니다.

### 기존 데이터 레이크 vs Paimon

| 항목 | Hive/Parquet | Delta Lake | Apache Iceberg | **Apache Paimon** |
|------|--------------|------------|----------------|-------------------|
| **실시간 업데이트** | X | O | O | **최적화** |
| **Flink 통합** | 제한적 | 제한적 | 좋음 | **네이티브** |
| **스트리밍 쓰기** | X | O | O | **최적화** |
| **ACID** | X | O | O | O |
| **Time Travel** | X | O | O | O |
| **Changelog** | X | 제한적 | 제한적 | **네이티브** |

### Paimon의 핵심 기능

#### 1. Changelog (변경 로그)

```
Kafka → Flink → Paimon

데이터 변경 기록:
+I (INSERT):  {"id": 1, "price": 100}
+U (UPDATE):  {"id": 1, "price": 150}  ← 가격 변경
-D (DELETE):  {"id": 1}                ← 삭제

Paimon은 모든 변경을 추적하여 저장
→ 특정 시점으로 되돌리기 가능 (Time Travel)
```

#### 2. Merge-on-Read vs Copy-on-Write

```
Merge-on-Read (기본값, 스트리밍에 적합):
- 쓰기 시: 변경분만 별도 파일에 저장 (빠름)
- 읽기 시: 기존 데이터 + 변경분 병합 (약간 느림)
- 적합: 쓰기가 많은 실시간 워크로드

Copy-on-Write:
- 쓰기 시: 전체 파일 다시 쓰기 (느림)
- 읽기 시: 바로 읽기 (빠름)
- 적합: 읽기가 많은 분석 워크로드
```

#### 3. 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     Apache Paimon                            │
│                                                              │
│  ┌─────────────────┐     ┌─────────────────────────────┐    │
│  │   Catalog       │     │      Table Store            │    │
│  │  (메타데이터)    │     │  (실제 데이터 저장)          │    │
│  │                 │     │                             │    │
│  │  - 테이블 정의   │     │  ┌─────────────────────┐    │    │
│  │  - 스키마 정보   │     │  │   Snapshot (버전)   │    │    │
│  │  - 파티션 정보   │     │  │   - snapshot-1      │    │    │
│  │                 │     │  │   - snapshot-2      │    │    │
│  └─────────────────┘     │  └─────────────────────┘    │    │
│                          │  ┌─────────────────────┐    │    │
│                          │  │   Data Files        │    │    │
│                          │  │   - Parquet/ORC     │    │    │
│                          │  └─────────────────────┘    │    │
│                          └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   MinIO (S3 호환)    │
                    │   실제 파일 저장     │
                    └─────────────────────┘
```

---

## Docker Compose 설정

### MinIO 구성

```yaml
# docker-compose.yml (MinIO 부분)

  # ============================================
  # MinIO (S3 호환 스토리지 - Paimon 저장소)
  # ============================================
  minio:
    image: minio/minio:latest
    container_name: minio
    ports:
      - "9000:9000"   # S3 API
      - "9001:9001"   # Web Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    networks:
      - pipeline-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512M

  # MinIO 초기 버킷 생성
  minio-init:
    image: minio/mc:latest
    container_name: minio-init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set myminio http://minio:9000 minioadmin minioadmin;
      mc mb myminio/paimon --ignore-existing;
      mc mb myminio/checkpoints --ignore-existing;
      mc mb myminio/warehouse --ignore-existing;
      echo 'Buckets created successfully';
      exit 0;
      "
    networks:
      - pipeline-network
```

### 설정 항목 설명

| 설정 | 값 | 설명 |
|------|-----|------|
| `MINIO_ROOT_USER` | minioadmin | 관리자 계정 |
| `MINIO_ROOT_PASSWORD` | minioadmin | 관리자 비밀번호 |
| Port 9000 | S3 API | 애플리케이션 접속용 |
| Port 9001 | Web Console | 브라우저 관리용 |

### 생성되는 버킷

| 버킷 | 용도 |
|------|------|
| `paimon` | Paimon 테이블 데이터 |
| `checkpoints` | Flink 체크포인트 |
| `warehouse` | 기타 데이터 웨어하우스 |

---

## MinIO 사용하기

### 1. 클러스터 시작

```bash
docker compose up -d

# MinIO 상태 확인
docker compose ps minio
```

### 2. Web Console 접속

브라우저에서 http://localhost:9001 접속

**로그인 정보:**
- Username: `minioadmin`
- Password: `minioadmin`

### 3. CLI (mc) 사용

```bash
# MinIO Client 설치 (Mac)
brew install minio/stable/mc

# 로컬 MinIO 등록
mc alias set local http://localhost:9000 minioadmin minioadmin

# 버킷 목록
mc ls local

# 파일 업로드
mc cp data.parquet local/warehouse/

# 파일 목록
mc ls local/warehouse/

# 파일 다운로드
mc cp local/warehouse/data.parquet ./downloaded.parquet
```

### 4. Python (boto3) 사용

```python
import boto3
from botocore.client import Config

# MinIO 클라이언트 생성
s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin',
    config=Config(signature_version='s3v4')
)

# 버킷 목록
buckets = s3.list_buckets()
for bucket in buckets['Buckets']:
    print(f"  {bucket['Name']}")

# 파일 업로드
s3.upload_file('local_file.parquet', 'warehouse', 'data/file.parquet')

# 파일 다운로드
s3.download_file('warehouse', 'data/file.parquet', 'downloaded.parquet')

# 파일 목록
response = s3.list_objects_v2(Bucket='warehouse', Prefix='data/')
for obj in response.get('Contents', []):
    print(f"  {obj['Key']} ({obj['Size']} bytes)")
```

---

## Paimon 테이블 생성

### Flink SQL에서 Paimon 카탈로그 설정

```bash
# Flink SQL Client 접속
docker exec -it flink-jobmanager /opt/flink/bin/sql-client.sh
```

### 1. Paimon 카탈로그 생성

```sql
-- Paimon 카탈로그 생성 (MinIO에 저장)
CREATE CATALOG paimon_catalog WITH (
    'type' = 'paimon',
    'warehouse' = 's3://paimon/warehouse',
    's3.endpoint' = 'http://minio:9000',
    's3.access-key' = 'minioadmin',
    's3.secret-key' = 'minioadmin',
    's3.path.style.access' = 'true'
);

-- 카탈로그 사용
USE CATALOG paimon_catalog;

-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS upbit;
USE upbit;
```

### 2. Paimon 테이블 생성

```sql
-- 업비트 티커 테이블 (Primary Key 테이블)
CREATE TABLE ticker (
    symbol STRING,
    price DOUBLE,
    volume DOUBLE,
    change_rate DOUBLE,
    trade_timestamp TIMESTAMP(3),
    dt STRING,  -- 파티션 키
    PRIMARY KEY (symbol, dt) NOT ENFORCED
) PARTITIONED BY (dt)
WITH (
    'changelog-producer' = 'input',
    'merge-engine' = 'deduplicate',
    'bucket' = '4'
);
```

### 테이블 옵션 설명

| 옵션 | 값 | 설명 |
|------|-----|------|
| `changelog-producer` | input | 입력 데이터에서 changelog 생성 |
| `merge-engine` | deduplicate | 같은 PK는 최신 값으로 중복 제거 |
| `bucket` | 4 | 버킷 수 (병렬 처리 단위) |

### 3. Kafka → Paimon 스트리밍

```sql
-- Kafka 소스 테이블
CREATE TEMPORARY TABLE kafka_ticker (
    symbol STRING,
    price DOUBLE,
    volume DOUBLE,
    change_rate DOUBLE,
    trade_timestamp TIMESTAMP(3),
    proc_time AS PROCTIME()
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-ticker',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'properties.group.id' = 'paimon-writer',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json'
);

-- Kafka → Paimon 스트리밍 INSERT
INSERT INTO ticker
SELECT 
    symbol,
    price,
    volume,
    change_rate,
    trade_timestamp,
    DATE_FORMAT(trade_timestamp, 'yyyy-MM-dd') AS dt
FROM kafka_ticker;
```

### 4. Time Travel 쿼리

```sql
-- 현재 데이터
SELECT * FROM ticker WHERE symbol = 'BTC' LIMIT 10;

-- 1시간 전 데이터 (Time Travel)
SELECT * FROM ticker /*+ OPTIONS('scan.timestamp-millis' = '1704067200000') */
WHERE symbol = 'BTC';

-- 특정 스냅샷 버전 데이터
SELECT * FROM ticker /*+ OPTIONS('scan.snapshot-id' = '5') */
WHERE symbol = 'BTC';
```

---

## MinIO + Paimon 데이터 구조

저장된 데이터 구조 확인:

```bash
mc ls local/paimon/warehouse/upbit.db/ticker/ --recursive
```

```
warehouse/
└── upbit.db/
    └── ticker/
        ├── dt=2024-01-01/
        │   ├── bucket-0/
        │   │   ├── data-xxx.parquet
        │   │   └── data-yyy.parquet
        │   └── bucket-1/
        │       └── data-zzz.parquet
        ├── dt=2024-01-02/
        │   └── ...
        ├── manifest/
        │   ├── manifest-xxx
        │   └── manifest-list-xxx
        ├── schema/
        │   └── schema-0
        └── snapshot/
            ├── snapshot-1
            ├── snapshot-2
            └── LATEST
```

| 디렉토리 | 용도 |
|----------|------|
| `dt=yyyy-MM-dd/` | 날짜별 파티션 |
| `bucket-N/` | 버킷별 데이터 파일 |
| `manifest/` | 파일 목록 메타데이터 |
| `schema/` | 스키마 버전 관리 |
| `snapshot/` | 스냅샷 (버전) 정보 |

---

## 문제 해결

### MinIO 연결 실패

```bash
# 헬스체크 확인
curl http://localhost:9000/minio/health/live

# 컨테이너 로그
docker compose logs minio
```

### Paimon S3 접근 에러

Flink에서 S3 접근 시 필요한 설정:
```yaml
s3.endpoint: http://minio:9000
s3.path-style-access: true  # 중요! MinIO는 path-style 필요
s3.access-key: minioadmin
s3.secret-key: minioadmin
```

### 버킷이 생성되지 않을 때

```bash
# 수동 버킷 생성
docker exec minio-init mc mb myminio/paimon

# 또는 MinIO Console에서 직접 생성
# http://localhost:9001 → Buckets → Create Bucket
```

---

## 다음 단계

데이터 레이크 스토리지가 준비되었습니다. 다음 글에서는 **Cursor MCP**를 설정하여 AI 기반 개발 환경을 구축합니다.

[다음 글: Cursor MCP 개발 환경 설정 →](./05-cursor-mcp-설정.md)
