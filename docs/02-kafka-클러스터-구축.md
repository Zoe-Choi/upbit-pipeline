# M1 맥북에서 Kafka 클러스터 구축하기 (KRaft 모드)

> Zookeeper 없이 Kafka 자체만으로 3노드 클러스터를 구축합니다.

## 시리즈 목차

1. [프로젝트 개요](./01-프로젝트-개요.md)
2. **Kafka 클러스터 구축 (KRaft 모드)** (현재 글)
3. [Flink 클러스터 구축](./03-flink-클러스터-구축.md)
4. [MinIO + Apache Paimon 스토리지](./04-minio-paimon-스토리지.md)
5. [Cursor MCP 개발 환경 설정](./05-cursor-mcp-설정.md)

---

## Apache Kafka란?

### 개요

**Apache Kafka**는 LinkedIn에서 개발한 **분산 이벤트 스트리밍 플랫폼**입니다. 대용량 실시간 데이터를 안정적으로 수집, 저장, 처리할 수 있습니다.

### 핵심 개념

```
Producer ──▶ Topic (Partition 0) ──▶ Consumer Group
             Topic (Partition 1)
             Topic (Partition 2)
```

| 용어 | 설명 |
|------|------|
| **Producer** | 메시지를 Kafka로 보내는 클라이언트 |
| **Consumer** | 메시지를 Kafka에서 읽는 클라이언트 |
| **Topic** | 메시지 카테고리 (예: upbit-ticker) |
| **Partition** | Topic의 물리적 분할 단위 (병렬 처리 가능) |
| **Broker** | Kafka 서버 인스턴스 |
| **Consumer Group** | 파티션을 나눠 처리하는 Consumer 집합 |

### 왜 Kafka를 사용하나?

1. **고가용성**: 브로커 장애 시에도 서비스 지속
2. **확장성**: 브로커/파티션 추가로 수평 확장
3. **내구성**: 디스크에 영구 저장, 복제본 유지
4. **높은 처리량**: 초당 수백만 메시지 처리 가능
5. **실시간 처리**: 밀리초 단위 지연

---

## Zookeeper vs KRaft 모드

### 기존 방식: Zookeeper

Kafka 2.x 이전에는 **Zookeeper**가 필수였습니다.

```
┌─────────────┐     ┌─────────────┐
│  Zookeeper  │◀───▶│  Zookeeper  │
│   Node 1    │     │   Node 2    │
└─────────────┘     └─────────────┘
       ▲                   ▲
       │     메타데이터     │
       ▼        관리        ▼
┌─────────────────────────────────┐
│        Kafka Brokers            │
└─────────────────────────────────┘
```

**Zookeeper의 역할:**
- 브로커 등록 및 상태 관리
- 리더 선출
- 토픽/파티션 메타데이터 저장
- 컨슈머 그룹 코디네이션

**문제점:**
- 별도 클러스터 운영 필요 (복잡성 증가)
- 리소스 추가 소비 (특히 메모리)
- 장애 포인트 증가
- 확장 시 Zookeeper도 함께 확장 필요

### 새로운 방식: KRaft 모드

Kafka 3.x부터 **KRaft (Kafka Raft)** 모드가 도입되었습니다.

```
┌─────────────────────────────────────────┐
│           Kafka Brokers                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │Broker 1 │ │Broker 2 │ │Broker 3 │    │
│  │+Ctrl    │ │+Ctrl    │ │+Ctrl    │    │
│  └─────────┘ └─────────┘ └─────────┘    │
│                                          │
│  내장 Raft 프로토콜로 메타데이터 관리     │
└─────────────────────────────────────────┘
```

**KRaft의 장점:**

| 항목 | Zookeeper | KRaft |
|------|-----------|-------|
| 아키텍처 | Kafka + ZK 클러스터 | Kafka만 |
| 메모리 | +1~2GB (ZK용) | 절약 |
| 운영 복잡도 | 높음 | 낮음 |
| 장애 포인트 | 2개 시스템 | 1개 시스템 |
| 확장성 | ZK도 함께 확장 | Kafka만 확장 |
| 복구 시간 | 느림 | 빠름 |

> **결론**: 16GB RAM 환경에서는 KRaft 모드가 필수입니다.

---

## Docker Compose 설정

### 전체 구성

```yaml
# docker-compose.yml (Kafka 부분)

services:
  kafka-1:
    image: apache/kafka:latest
    container_name: kafka-1
    ports:
      - "9092:9092"      # 내부 통신
      - "29092:29092"    # 외부 접속 (localhost)
    environment:
      # 노드 식별
      KAFKA_NODE_ID: 1
      
      # KRaft 모드: controller + broker 역할 동시 수행
      KAFKA_PROCESS_ROLES: broker,controller
      
      # 리스너 설정
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093,EXTERNAL://:29092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-1:9092,EXTERNAL://localhost:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT,EXTERNAL:PLAINTEXT
      
      # Controller 설정
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
      
      # 토픽 기본 설정
      KAFKA_NUM_PARTITIONS: 3
      KAFKA_DEFAULT_REPLICATION_FACTOR: 3
      KAFKA_MIN_INSYNC_REPLICAS: 2
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      
      # 클러스터 ID (모든 브로커 동일해야 함)
      CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk
      
      # 메모리 최적화
      KAFKA_HEAP_OPTS: -Xmx256m -Xms128m
    volumes:
      - kafka_1_data:/var/lib/kafka/data
    networks:
      - pipeline-network
    deploy:
      resources:
        limits:
          memory: 512M
```

### 설정 항목 상세 설명

#### 1. KAFKA_PROCESS_ROLES

```yaml
KAFKA_PROCESS_ROLES: broker,controller
```

| 값 | 설명 |
|-----|------|
| `broker` | 클라이언트 요청 처리, 데이터 저장 |
| `controller` | 메타데이터 관리, 리더 선출 |
| `broker,controller` | 둘 다 수행 (소규모 클러스터에 적합) |

> 대규모 클러스터에서는 controller 전용 노드를 분리하기도 합니다.

#### 2. 리스너 구성

```yaml
KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093,EXTERNAL://:29092
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-1:9092,EXTERNAL://localhost:29092
```

```
┌─────────────────────────────────────────────────┐
│                 Kafka Broker                     │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ PLAINTEXT   │  │ CONTROLLER  │  │ EXTERNAL │ │
│  │   :9092     │  │   :9093     │  │  :29092  │ │
│  │ (브로커간)   │  │ (컨트롤러)  │  │(외부접속)│ │
│  └─────────────┘  └─────────────┘  └──────────┘ │
└─────────────────────────────────────────────────┘
```

| 리스너 | 포트 | 용도 |
|--------|------|------|
| PLAINTEXT | 9092 | 브로커 간 내부 통신 |
| CONTROLLER | 9093 | KRaft 컨트롤러 통신 |
| EXTERNAL | 29092~4 | 호스트에서 접속 (localhost) |

#### 3. Controller Quorum Voters

```yaml
KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
```

Raft 프로토콜에서 투표에 참여할 컨트롤러 목록입니다.

- 형식: `{node_id}@{host}:{controller_port}`
- 과반수(2/3) 이상 살아있어야 클러스터 정상 동작
- 리더 선출 시 투표에 사용

#### 4. 복제 및 안정성 설정

```yaml
KAFKA_DEFAULT_REPLICATION_FACTOR: 3
KAFKA_MIN_INSYNC_REPLICAS: 2
```

```
Topic: upbit-ticker (Partition 0)

┌─────────┐    ┌─────────┐    ┌─────────┐
│Broker 1 │    │Broker 2 │    │Broker 3 │
│ LEADER  │───▶│ REPLICA │───▶│ REPLICA │
│ (ISR)   │    │ (ISR)   │    │ (ISR)   │
└─────────┘    └─────────┘    └─────────┘
```

| 설정 | 값 | 의미 |
|------|-----|------|
| `replication.factor` | 3 | 각 파티션을 3개 브로커에 복제 |
| `min.insync.replicas` | 2 | 최소 2개 복제본이 동기화되어야 쓰기 성공 |

> 브로커 1대 장애 시에도 데이터 손실 없이 서비스 지속 가능

---

## 클러스터 시작하기

### 1. 시작

```bash
cd upbit-pipeline

# 클러스터 시작
docker compose up -d

# 상태 확인
docker compose ps
```

예상 출력:
```
NAME         IMAGE                COMMAND                  STATUS          PORTS
kafka-1      apache/kafka:latest  "/__cacert_entrypoin…"   Up 30 seconds   0.0.0.0:9092->9092/tcp, 0.0.0.0:29092->29092/tcp
kafka-2      apache/kafka:latest  "/__cacert_entrypoin…"   Up 30 seconds   0.0.0.0:9093->9092/tcp, 0.0.0.0:29093->29093/tcp
kafka-3      apache/kafka:latest  "/__cacert_entrypoin…"   Up 30 seconds   0.0.0.0:9094->9092/tcp, 0.0.0.0:29094->29094/tcp
kafka-ui     provectuslabs/kafka  "/bin/sh -c 'java --…"   Up 30 seconds   0.0.0.0:8080->8080/tcp
```

### 2. 로그 확인

```bash
# 특정 브로커 로그
docker compose logs kafka-1

# 모든 Kafka 로그 실시간
docker compose logs -f kafka-1 kafka-2 kafka-3
```

정상 시작 시 로그:
```
[KafkaRaftServer nodeId=1] Kafka Server started
```

### 3. Kafka UI 접속

브라우저에서 http://localhost:8080 접속

![Kafka UI](https://via.placeholder.com/800x400?text=Kafka+UI+Dashboard)

---

## 클러스터 테스트

### 1. 토픽 생성

```bash
# kafka-1 컨테이너에서 토픽 생성
docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --topic upbit-ticker \
  --partitions 3 \
  --replication-factor 3
```

### 2. 토픽 확인

```bash
docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic upbit-ticker
```

출력:
```
Topic: upbit-ticker	TopicId: ABC123...
	PartitionCount: 3	ReplicationFactor: 3
	Partition: 0	Leader: 1	Replicas: 1,2,3	Isr: 1,2,3
	Partition: 1	Leader: 2	Replicas: 2,3,1	Isr: 2,3,1
	Partition: 2	Leader: 3	Replicas: 3,1,2	Isr: 3,1,2
```

- **Leader**: 해당 파티션의 읽기/쓰기 담당 브로커
- **Replicas**: 복제본을 가진 브로커 목록
- **Isr (In-Sync Replicas)**: 동기화된 복제본 (리더 포함)

### 3. 메시지 테스트

**Producer (메시지 전송):**
```bash
docker exec -it kafka-1 /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic upbit-ticker
```

입력:
```
{"symbol": "BTC", "price": 50000000}
{"symbol": "ETH", "price": 3000000}
```

**Consumer (메시지 수신):**
```bash
docker exec kafka-1 /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic upbit-ticker \
  --from-beginning
```

---

## Python 클라이언트 예제

### 설치

```bash
pip install kafka-python
```

### Producer

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:29092', 'localhost:29093', 'localhost:29094'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    acks='all',  # 모든 ISR에 복제 후 응답
    retries=3
)

# 메시지 전송
data = {'symbol': 'BTC', 'price': 50000000, 'timestamp': '2024-01-01T00:00:00'}
future = producer.send('upbit-ticker', value=data)

# 전송 확인
result = future.get(timeout=10)
print(f"Sent to partition {result.partition}, offset {result.offset}")

producer.close()
```

### Consumer

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'upbit-ticker',
    bootstrap_servers=['localhost:29092', 'localhost:29093', 'localhost:29094'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    group_id='my-consumer-group',
    enable_auto_commit=True
)

for message in consumer:
    print(f"Partition: {message.partition}")
    print(f"Offset: {message.offset}")
    print(f"Value: {message.value}")
    print("---")
```

---

## 문제 해결

### 브로커가 시작되지 않을 때

```bash
# 로그 확인
docker compose logs kafka-1 | tail -50

# 흔한 문제: CLUSTER_ID 불일치
# 해결: 볼륨 삭제 후 재시작
docker compose down -v
docker compose up -d
```

### 외부에서 연결 안 될 때

`KAFKA_ADVERTISED_LISTENERS`가 올바른지 확인:
- Docker 내부: `kafka-1:9092`
- 호스트에서: `localhost:29092`

### 메모리 부족 시

```bash
# 현재 메모리 사용량 확인
docker stats --no-stream

# 필요시 KAFKA_HEAP_OPTS 조정
KAFKA_HEAP_OPTS: -Xmx128m -Xms64m  # 더 작게
```

---

## 다음 단계

Kafka 클러스터가 준비되었습니다. 다음 글에서는 **Flink 클러스터**를 구축하여 실시간 스트림 처리를 설정합니다.

[다음 글: Flink 클러스터 구축 →](./03-flink-클러스터-구축.md)
