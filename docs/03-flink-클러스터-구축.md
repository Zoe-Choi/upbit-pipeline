# M1 맥북에서 Flink 클러스터 구축하기

> JobManager 1개 + TaskManager 2개로 실제 운영환경과 유사한 분산 처리 환경을 구축합니다.

## 시리즈 목차

1. [프로젝트 개요](./01-프로젝트-개요.md)
2. [Kafka 클러스터 구축 (KRaft 모드)](./02-kafka-클러스터-구축.md)
3. **Flink 클러스터 구축** (현재 글)
4. [MinIO + Apache Paimon 스토리지](./04-minio-paimon-스토리지.md)
5. [Cursor MCP 개발 환경 설정](./05-cursor-mcp-설정.md)

---

## Apache Flink란?

### 개요

**Apache Flink**는 **분산 스트림 처리 프레임워크**입니다. 실시간 데이터를 낮은 지연시간으로 처리하면서도, 배치 처리까지 지원하는 통합 엔진입니다.

### Spark vs Flink

| 항목 | Apache Spark | Apache Flink |
|------|--------------|--------------|
| **처리 모델** | 마이크로 배치 | 네이티브 스트리밍 |
| **지연 시간** | 초 단위 | 밀리초 단위 |
| **상태 관리** | 제한적 | 강력 (Stateful) |
| **Exactly-Once** | Structured Streaming | 네이티브 지원 |
| **적합 용도** | 대용량 배치, ML | 실시간 분석, CEP |

> **선택 기준**: 실시간 가격 데이터 처리에는 **밀리초 단위 지연**이 중요하므로 Flink가 적합합니다.

### Flink 핵심 개념

```
┌─────────────────────────────────────────────────────────────┐
│                     Flink Cluster                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               JobManager (Master)                    │    │
│  │  - Job 스케줄링                                      │    │
│  │  - 체크포인트 조율                                   │    │
│  │  - 장애 복구 관리                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│              Task 할당     │                                  │
│                           ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              TaskManagers (Workers)                    │  │
│  │  ┌─────────────────┐      ┌─────────────────┐         │  │
│  │  │  TaskManager 1  │      │  TaskManager 2  │         │  │
│  │  │  ┌────┐ ┌────┐ │      │  ┌────┐ ┌────┐ │         │  │
│  │  │  │Slot│ │Slot│ │      │  │Slot│ │Slot│ │         │  │
│  │  │  │ 1  │ │ 2  │ │      │  │ 1  │ │ 2  │ │         │  │
│  │  │  └────┘ └────┘ │      │  └────┘ └────┘ │         │  │
│  │  └─────────────────┘      └─────────────────┘         │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

| 용어 | 설명 |
|------|------|
| **JobManager** | 작업 조율자. 스케줄링, 체크포인트, 장애 복구 담당 |
| **TaskManager** | 실제 작업 수행자. 여러 개의 Slot 보유 |
| **Slot** | TaskManager 내 실행 단위. 병렬 처리의 기본 단위 |
| **Job** | 사용자가 제출한 데이터 처리 작업 |
| **Task** | Job을 구성하는 개별 연산 단위 |

### Slot과 병렬 처리

```
Job: Source → Map → Sink (병렬도: 4)

TaskManager 1 (2 slots)     TaskManager 2 (2 slots)
┌──────────────────┐        ┌──────────────────┐
│ Slot 1           │        │ Slot 1           │
│ Source[0]→Map→..│        │ Source[2]→Map→..│
├──────────────────┤        ├──────────────────┤
│ Slot 2           │        │ Slot 2           │
│ Source[1]→Map→..│        │ Source[3]→Map→..│
└──────────────────┘        └──────────────────┘

총 병렬도 = 2 TaskManagers × 2 Slots = 4
```

---

## 상태 관리와 체크포인트

### Stateful 스트림 처리

Flink의 강력한 기능 중 하나는 **상태(State) 관리**입니다.

```java
// 예: 이동 평균 계산 - 이전 데이터를 "기억"해야 함
stream
    .keyBy(event -> event.getSymbol())  // BTC, ETH 등으로 그룹화
    .process(new MovingAverageFunction())  // 상태 보관
```

상태 저장소 옵션:

| Backend | 특징 | 적합 용도 |
|---------|------|----------|
| **HashMapStateBackend** | 메모리 저장, 빠름 | 작은 상태, 개발 환경 |
| **RocksDBStateBackend** | 디스크 저장, 대용량 | 큰 상태, 프로덕션 |

### 체크포인트 (Checkpoint)

**체크포인트**는 특정 시점의 상태를 스냅샷으로 저장하는 것입니다.

```
시간 ─────────────────────────────────────────────▶

     │ CP1        │ CP2        │ CP3
     ▼            ▼            ▼
[State]────▶[State]────▶[State]────▶...
                              │
                              │ 장애 발생!
                              ▼
                         [CP3에서 복구]
```

**장점:**
- 장애 발생 시 마지막 체크포인트에서 재시작
- Exactly-Once 처리 보장
- 외부 스토리지(S3, MinIO)에 저장 가능

---

## Docker Compose 설정

### Flink 클러스터 구성

```yaml
# docker-compose.yml (Flink 부분)

  # ============================================
  # Flink Cluster (1 JobManager + 2 TaskManagers)
  # ============================================
  flink-jobmanager:
    image: flink:1.18-scala_2.12-java11
    container_name: flink-jobmanager
    ports:
      - "8081:8081"  # Flink Web UI
    command: jobmanager
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: flink-jobmanager
        jobmanager.memory.process.size: 512m
        state.backend: rocksdb
        state.checkpoints.dir: s3://paimon/checkpoints
        state.savepoints.dir: s3://paimon/savepoints
        s3.endpoint: http://minio:9000
        s3.path-style-access: true
        s3.access-key: minioadmin
        s3.secret-key: minioadmin
    networks:
      - pipeline-network
    deploy:
      resources:
        limits:
          memory: 768M

  flink-taskmanager-1:
    image: flink:1.18-scala_2.12-java11
    container_name: flink-taskmanager-1
    command: taskmanager
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: flink-jobmanager
        taskmanager.memory.process.size: 1g
        taskmanager.numberOfTaskSlots: 2
        state.backend: rocksdb
        s3.endpoint: http://minio:9000
        s3.path-style-access: true
        s3.access-key: minioadmin
        s3.secret-key: minioadmin
    networks:
      - pipeline-network
    depends_on:
      - flink-jobmanager
    deploy:
      resources:
        limits:
          memory: 1280M

  flink-taskmanager-2:
    image: flink:1.18-scala_2.12-java11
    container_name: flink-taskmanager-2
    command: taskmanager
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: flink-jobmanager
        taskmanager.memory.process.size: 1g
        taskmanager.numberOfTaskSlots: 2
        state.backend: rocksdb
        s3.endpoint: http://minio:9000
        s3.path-style-access: true
        s3.access-key: minioadmin
        s3.secret-key: minioadmin
    networks:
      - pipeline-network
    depends_on:
      - flink-jobmanager
    deploy:
      resources:
        limits:
          memory: 1280M
```

### 설정 항목 상세 설명

#### 1. 메모리 설정

```yaml
jobmanager.memory.process.size: 512m
taskmanager.memory.process.size: 1g
```

**Flink 메모리 구조:**

```
┌─────────────────────────────────────────┐
│         Total Process Memory            │
│  ┌───────────────────────────────────┐  │
│  │         JVM Heap                  │  │
│  │  ┌─────────────┐ ┌─────────────┐  │  │
│  │  │ Framework   │ │   Task      │  │  │
│  │  │   Heap      │ │   Heap      │  │  │
│  │  └─────────────┘ └─────────────┘  │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │    Off-Heap (Native, Network)     │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │      JVM Metaspace & Overhead     │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

| 메모리 영역 | 용도 |
|------------|------|
| Task Heap | 사용자 코드 실행 |
| Framework Heap | Flink 내부 자료구조 |
| Managed Memory | RocksDB, 배치 정렬 등 |
| Network | 셔플 버퍼 |

#### 2. Task Slots 설정

```yaml
taskmanager.numberOfTaskSlots: 2
```

| 설정 | 값 | 의미 |
|------|-----|------|
| TaskManager 수 | 2개 | 독립 프로세스/컨테이너 |
| Slots per TM | 2개 | TM당 동시 실행 가능 태스크 |
| **총 병렬도** | **4** | 2 × 2 = 4 |

> **팁**: Slots 수는 보통 CPU 코어 수와 맞추는 것이 좋습니다.

#### 3. State Backend 설정

```yaml
state.backend: rocksdb
state.checkpoints.dir: s3://paimon/checkpoints
state.savepoints.dir: s3://paimon/savepoints
```

| 설정 | 값 | 설명 |
|------|-----|------|
| `state.backend` | rocksdb | RocksDB로 상태 저장 (대용량 지원) |
| `checkpoints.dir` | S3 경로 | 자동 체크포인트 저장 위치 |
| `savepoints.dir` | S3 경로 | 수동 세이브포인트 저장 위치 |

---

## 클러스터 시작 및 확인

### 1. 시작

```bash
docker compose up -d

# Flink 컨테이너 확인
docker compose ps | grep flink
```

예상 출력:
```
flink-jobmanager     flink:1.18-...   "..."   Up   0.0.0.0:8081->8081/tcp
flink-taskmanager-1  flink:1.18-...   "..."   Up   
flink-taskmanager-2  flink:1.18-...   "..."   Up   
```

### 2. Flink Web UI 접속

브라우저에서 http://localhost:8081 접속

**Dashboard 확인 사항:**
- Available Task Slots: 4 (2 TM × 2 slots)
- TaskManagers: 2
- Free Slots: 4 (작업 없을 때)

### 3. 로그 확인

```bash
# JobManager 로그
docker compose logs flink-jobmanager

# TaskManager 로그
docker compose logs flink-taskmanager-1
```

정상 시작 시:
```
Starting the JobManager.
...
Registering TaskManager with ResourceID ... at ResourceManager
```

---

## Flink SQL 예제

### Kafka 연동 테스트

Flink SQL Client로 Kafka 데이터를 쿼리하는 예제입니다.

```bash
# Flink SQL Client 접속
docker exec -it flink-jobmanager /opt/flink/bin/sql-client.sh
```

### 1. Kafka 소스 테이블 생성

```sql
CREATE TABLE upbit_ticker (
    symbol STRING,
    price DOUBLE,
    volume DOUBLE,
    `timestamp` TIMESTAMP(3),
    WATERMARK FOR `timestamp` AS `timestamp` - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-ticker',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'properties.group.id' = 'flink-consumer',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'json'
);
```

### 2. 실시간 집계 쿼리

```sql
-- 5분 윈도우 평균 가격
SELECT 
    symbol,
    TUMBLE_START(`timestamp`, INTERVAL '5' MINUTE) AS window_start,
    AVG(price) AS avg_price,
    MAX(price) AS max_price,
    MIN(price) AS min_price,
    SUM(volume) AS total_volume
FROM upbit_ticker
GROUP BY 
    symbol,
    TUMBLE(`timestamp`, INTERVAL '5' MINUTE);
```

### 3. 결과를 다른 Kafka 토픽으로 출력

```sql
CREATE TABLE ticker_aggregates (
    symbol STRING,
    window_start TIMESTAMP(3),
    avg_price DOUBLE,
    max_price DOUBLE,
    min_price DOUBLE,
    total_volume DOUBLE
) WITH (
    'connector' = 'kafka',
    'topic' = 'upbit-ticker-aggregates',
    'properties.bootstrap.servers' = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    'format' = 'json'
);

INSERT INTO ticker_aggregates
SELECT 
    symbol,
    TUMBLE_START(`timestamp`, INTERVAL '5' MINUTE),
    AVG(price),
    MAX(price),
    MIN(price),
    SUM(volume)
FROM upbit_ticker
GROUP BY symbol, TUMBLE(`timestamp`, INTERVAL '5' MINUTE);
```

---

## Python PyFlink 예제

### 설치

```bash
pip install apache-flink==1.18.0
```

### 간단한 스트리밍 작업

```python
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings

# 환경 설정
env = StreamExecutionEnvironment.get_execution_environment()
env.set_parallelism(4)

settings = EnvironmentSettings.new_instance() \
    .in_streaming_mode() \
    .build()
    
table_env = StreamTableEnvironment.create(env, settings)

# Kafka 소스 테이블
table_env.execute_sql("""
    CREATE TABLE upbit_ticker (
        symbol STRING,
        price DOUBLE,
        `timestamp` TIMESTAMP(3),
        WATERMARK FOR `timestamp` AS `timestamp` - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'upbit-ticker',
        'properties.bootstrap.servers' = 'localhost:29092',
        'properties.group.id' = 'pyflink-consumer',
        'scan.startup.mode' = 'latest-offset',
        'format' = 'json'
    )
""")

# 실시간 쿼리
result = table_env.sql_query("""
    SELECT symbol, price, `timestamp`
    FROM upbit_ticker
    WHERE price > 50000000
""")

# 콘솔 출력
result.execute().print()
```

---

## 문제 해결

### TaskManager가 등록되지 않을 때

```bash
# 네트워크 확인
docker network inspect upbit-pipeline_pipeline-network

# JobManager 로그에서 에러 확인
docker compose logs flink-jobmanager | grep -i error
```

### 메모리 부족 (OOM)

```yaml
# TaskManager 메모리 줄이기
taskmanager.memory.process.size: 768m
taskmanager.numberOfTaskSlots: 1  # Slot 수도 줄이기
```

### 체크포인트 실패

```bash
# MinIO 연결 확인
docker compose logs flink-jobmanager | grep -i s3

# MinIO가 정상인지 확인
curl http://localhost:9000/minio/health/live
```

---

## 다음 단계

Flink 클러스터가 준비되었습니다. 다음 글에서는 **MinIO와 Apache Paimon**을 설정하여 스트리밍 데이터 레이크를 구축합니다.

[다음 글: MinIO + Apache Paimon 스토리지 →](./04-minio-paimon-스토리지.md)
