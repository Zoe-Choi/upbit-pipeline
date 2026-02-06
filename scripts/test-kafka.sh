#!/bin/bash
# ============================================
# Kafka Topic Testing Script
# ============================================
set -e

echo "========================================="
echo "Kafka Topic Test"
echo "========================================="

# Load environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"
TOPIC_TICKER="${KAFKA_TOPIC_TICKER:-upbit-ticker}"
TOPIC_TRADE="${KAFKA_TOPIC_TRADE:-upbit-trade}"

echo "Bootstrap Servers: $BOOTSTRAP"
echo ""

# List topics
echo "1. Listing topics..."
docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server kafka-1:9092 \
    --list

echo ""
echo "2. Topic details:"

for topic in "$TOPIC_TICKER" "$TOPIC_TRADE"; do
    echo ""
    echo "--- $topic ---"
    docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh \
        --bootstrap-server kafka-1:9092 \
        --describe \
        --topic "$topic" 2>/dev/null || echo "Topic not found: $topic"
done

echo ""
echo "3. Consumer group status:"
docker exec kafka-1 /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka-1:9092 \
    --list 2>/dev/null || echo "No consumer groups found"

echo ""
echo "4. Consume sample messages from $TOPIC_TICKER (Ctrl+C to stop):"
echo "   docker exec -it kafka-1 /opt/kafka/bin/kafka-console-consumer.sh \\"
echo "       --bootstrap-server kafka-1:9092 \\"
echo "       --topic $TOPIC_TICKER \\"
echo "       --from-beginning \\"
echo "       --max-messages 5"

echo ""
echo "========================================="
