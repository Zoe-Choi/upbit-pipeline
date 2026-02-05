#!/bin/bash

# Kafka 클러스터 삭제 스크립트 (Kubernetes)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$PROJECT_ROOT/kubernetes"

echo "🛑 Kubernetes에서 Kafka 클러스터를 삭제합니다..."

kubectl delete -f "$K8S_DIR/kafka-ui.yaml" --ignore-not-found
kubectl delete -f "$K8S_DIR/kafka.yaml" --ignore-not-found

read -p "Namespace와 PVC도 삭제하시겠습니까? (y/N): " confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    kubectl delete namespace kafka --ignore-not-found
    echo "✅ Namespace와 모든 리소스가 삭제되었습니다."
else
    echo "✅ Pod과 서비스만 삭제되었습니다. (PVC 유지)"
fi
