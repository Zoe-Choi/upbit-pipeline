#!/bin/bash

# Kafka 클러스터 시작 스크립트 (Docker Compose - KRaft 모드)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🚀 Kafka 클러스터를 시작합니다 (KRaft 모드)"
docker compose up -d

echo ""
echo "⏳ 클러스터가 준비될 때까지 대기 중..."
sleep 15

echo ""
echo "✅ Kafka 클러스터가 시작되었습니다!"
echo ""
echo "📊 접속 정보:"
echo "  - Kafka Broker 1: localhost:29092"
echo "  - Kafka Broker 2: localhost:29093"
echo "  - Kafka Broker 3: localhost:29094"
echo "  - Kafka UI: http://localhost:8080"
echo ""
echo "🔍 상태 확인: docker compose ps"
echo "📝 로그 확인: docker compose logs -f"
