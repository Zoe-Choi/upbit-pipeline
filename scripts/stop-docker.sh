#!/bin/bash

# Kafka 클러스터 중지 스크립트 (Docker Compose)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🛑 Kafka 클러스터를 중지합니다..."
docker compose down

echo "✅ 클러스터가 중지되었습니다."
echo ""
echo "💡 데이터 볼륨 삭제하려면: docker volume prune"
