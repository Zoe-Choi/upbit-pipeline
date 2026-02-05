#!/bin/bash

# Kafka 클러스터 시작 스크립트 (Kubernetes - KRaft 모드)
# 사전 요구사항: kubectl, minikube 또는 kind가 설치되어 있어야 합니다.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$PROJECT_ROOT/kubernetes"

echo "🚀 Kubernetes에 Kafka 클러스터를 배포합니다 (KRaft 모드)..."

# Kubernetes 클러스터 확인
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Kubernetes 클러스터에 연결할 수 없습니다."
    echo ""
    echo "💡 로컬 클러스터 시작 방법:"
    echo "  - Minikube: minikube start --memory 8192 --cpus 4"
    echo "  - Kind: kind create cluster --name upbit-pipeline"
    echo "  - Docker Desktop: Kubernetes 설정에서 활성화"
    exit 1
fi

echo "✅ Kubernetes 클러스터에 연결됨"
echo ""

# 매니페스트 적용
echo "📦 Namespace 생성..."
kubectl apply -f "$K8S_DIR/namespace.yaml"

echo "📦 Kafka 클러스터 배포 (KRaft 모드)..."
kubectl apply -f "$K8S_DIR/kafka.yaml"

echo "⏳ Kafka 브로커 준비 대기..."
kubectl wait --for=condition=ready pod -l app=kafka -n kafka --timeout=180s

echo "📦 Kafka UI 배포..."
kubectl apply -f "$K8S_DIR/kafka-ui.yaml"

echo ""
echo "✅ Kafka 클러스터가 배포되었습니다!"
echo ""
echo "📊 접속 정보:"
echo "  - Kafka Bootstrap: kafka-bootstrap.kafka.svc.cluster.local:9092"
echo "  - Kafka UI: kubectl port-forward svc/kafka-ui 8080:8080 -n kafka"
echo ""
echo "🔍 상태 확인:"
echo "  kubectl get pods -n kafka"
echo "  kubectl get svc -n kafka"
echo ""
echo "📝 로그 확인:"
echo "  kubectl logs -f -l app=kafka -n kafka"
