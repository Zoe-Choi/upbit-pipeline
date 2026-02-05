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
                        │     Data Processing / ML Pipeline   │
                        └─────────────────────────────────────┘
```

> KRaft 모드: Zookeeper 없이 Kafka 자체에서 메타데이터 관리 (리소스 절약)

## 빠른 시작

### 1. Docker Compose (개발 환경 - 권장)

```bash
# 스크립트 실행 권한 부여
chmod +x scripts/*.sh

# Kafka 클러스터 시작
./scripts/start-docker.sh

# 클러스터 테스트
./scripts/test-kafka.sh

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

| 서비스 | 주소 |
|--------|------|
| Kafka Broker 1 | `localhost:29092` |
| Kafka Broker 2 | `localhost:29093` |
| Kafka Broker 3 | `localhost:29094` |
| Kafka UI | http://localhost:8080 |

### Kubernetes

| 서비스 | 주소 |
|--------|------|
| Kafka Bootstrap | `kafka-bootstrap.kafka.svc.cluster.local:9092` |
| Kafka UI | `kubectl port-forward svc/kafka-ui 8080:8080 -n kafka` |

## 리소스 사용량 (M1 Pro 16GB 기준)

| 구성 요소 | 메모리 | CPU |
|-----------|--------|-----|
| Kafka Broker (x3) | 512MB x 3 | 0.5 core x 3 |
| Kafka UI | 512MB | 0.5 core |
| **총합** | **~2GB** | **~2 cores** |

> 다른 서비스(Flink, Spark, MinIO, Trino 등)를 위해 리소스를 최소화했습니다.

## 프로젝트 구조

```
upbit-pipeline/
├── docker-compose.yml          # Kafka 클러스터 (KRaft 모드)
├── kubernetes/
│   ├── namespace.yaml          # K8s 네임스페이스
│   ├── kafka.yaml              # Kafka StatefulSet (3 replicas, KRaft)
│   └── kafka-ui.yaml           # Kafka UI
└── scripts/
    ├── start-docker.sh         # Docker 클러스터 시작
    ├── stop-docker.sh          # Docker 클러스터 중지
    ├── start-k8s.sh            # K8s 클러스터 배포
    ├── stop-k8s.sh             # K8s 클러스터 삭제
    └── test-kafka.sh           # 클러스터 테스트
```

## Kafka 클러스터 설정

| 설정 | 값 | 설명 |
|------|-----|------|
| `num.partitions` | 3 | 기본 파티션 수 |
| `default.replication.factor` | 3 | 복제 계수 |
| `min.insync.replicas` | 2 | 최소 동기화 복제본 |
| `auto.create.topics.enable` | true | 자동 토픽 생성 |

## Python 연동 예시

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

### Kubernetes Pod Pending 상태

```bash
# 리소스 확인
kubectl describe pod -n kafka

# 노드 리소스 확인
kubectl top nodes
```

## 다음 단계

- [ ] 업비트 WebSocket 데이터 수집기 구현
- [ ] Apache Flink/Spark Streaming 연동
- [ ] 데이터 저장소 (TimescaleDB, ClickHouse) 추가
- [ ] ML 모델 학습 파이프라인 구축
- [ ] Prometheus + Grafana 모니터링

## 라이선스

MIT License
