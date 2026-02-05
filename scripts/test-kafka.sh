#!/bin/bash

# Kafka 클러스터 테스트 스크립트

set -e

TOPIC_NAME="test-topic"

echo "🧪 Kafka 클러스터 테스트를 시작합니다..."
echo ""

# 토픽 생성
echo "📝 테스트 토픽 생성..."
docker exec kafka-1 kafka-topics.sh \
    --bootstrap-server kafka-1:9092 \
    --create \
    --topic $TOPIC_NAME \
    --partitions 3 \
    --replication-factor 3 \
    --if-not-exists

echo ""
echo "📋 토픽 목록:"
docker exec kafka-1 kafka-topics.sh \
    --bootstrap-server kafka-1:9092 \
    --list

echo ""
echo "📊 토픽 상세 정보:"
docker exec kafka-1 kafka-topics.sh \
    --bootstrap-server kafka-1:9092 \
    --describe \
    --topic $TOPIC_NAME

echo ""
echo "✉️ 테스트 메시지 전송..."
echo "Hello Kafka from Upbit Pipeline!" | docker exec -i kafka-1 kafka-console-producer.sh \
    --bootstrap-server kafka-1:9092 \
    --topic $TOPIC_NAME

echo ""
echo "📨 메시지 수신 테스트..."
docker exec kafka-1 kafka-console-consumer.sh \
    --bootstrap-server kafka-1:9092 \
    --topic $TOPIC_NAME \
    --from-beginning \
    --max-messages 1

echo ""
echo "✅ Kafka 클러스터 테스트 완료!"
echo ""
echo "💡 Python에서 연결하기:"
echo '   from kafka import KafkaProducer'
echo '   producer = KafkaProducer(bootstrap_servers=["localhost:29092", "localhost:29093", "localhost:29094"])'
