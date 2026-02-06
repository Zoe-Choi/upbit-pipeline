#!/bin/bash
# ============================================
# MinIO Bucket Setup Script
# Creates required buckets for Paimon/Flink
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"

echo "MinIO Endpoint: $MINIO_ENDPOINT"
echo "========================================="

# Wait for MinIO to be ready
echo "Waiting for MinIO to be ready..."
for i in {1..30}; do
    if curl -s "$MINIO_ENDPOINT/minio/health/ready" > /dev/null 2>&1; then
        echo "MinIO is ready!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Configure mc (MinIO Client) alias
docker exec minio-1 mc alias set local http://localhost:9000 "$MINIO_USER" "$MINIO_PASSWORD" 2>/dev/null || true

# Create buckets
BUCKETS=("paimon" "warehouse" "checkpoints" "savepoints")

for bucket in "${BUCKETS[@]}"; do
    echo "Creating bucket: $bucket"
    docker exec minio-1 mc mb --ignore-existing local/$bucket 2>/dev/null || echo "Bucket $bucket already exists"
done

# Set bucket policies (public read for debugging)
echo "Setting bucket policies..."
docker exec minio-1 mc anonymous set download local/paimon 2>/dev/null || true

# List buckets
echo ""
echo "Created buckets:"
docker exec minio-1 mc ls local/

echo ""
echo "========================================="
echo "MinIO setup complete!"
echo "Console: http://localhost:9001"
echo "========================================="
