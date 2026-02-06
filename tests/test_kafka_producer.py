"""
Tests for Kafka producer.

Uses mocking to test producer behavior without requiring
an actual Kafka cluster.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, Any

from src.producers.kafka_producer import (
    UpbitKafkaProducer,
    ensure_topics_exist,
)
from src.config import KafkaConfig


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_kafka_config():
    """Mock Kafka configuration."""
    return KafkaConfig(
        bootstrap_servers="localhost:9092",
        topic_ticker="test-ticker",
        topic_trade="test-trade",
        topic_orderbook="test-orderbook",
    )


@pytest.fixture
def sample_ticker_message():
    """Sample ticker message for Kafka."""
    return {
        "market": "KRW-BTC",
        "trade_price": 50000000.0,
        "change": "RISE",
        "timestamp": 1707984000123,
    }


@pytest.fixture
def sample_trade_message():
    """Sample trade message for Kafka."""
    return {
        "market": "KRW-BTC",
        "trade_price": 50000000.0,
        "trade_volume": 0.1,
        "ask_bid": "BID",
        "sequential_id": 1707984000000001,
    }


@pytest.fixture
def sample_orderbook_message():
    """Sample orderbook message for Kafka."""
    return {
        "market": "KRW-BTC",
        "timestamp": 1707984000123,
        "total_ask_size": 100.0,
        "total_bid_size": 150.0,
        "best_ask_price": 50010000.0,
        "best_bid_price": 50000000.0,
    }


# =============================================================================
# Producer Initialization Tests
# =============================================================================


class TestProducerInitialization:
    """Tests for producer initialization."""

    @patch("src.producers.kafka_producer.Producer")
    def test_producer_created_with_correct_config(self, mock_producer_class):
        """Test producer is initialized with correct configuration."""
        # Reset singleton for testing
        UpbitKafkaProducer._instance = None

        config = KafkaConfig(
            bootstrap_servers="broker1:9092,broker2:9092",
            acks="all",
            retries=5,
            linger_ms=20,
            batch_size=32768,
            compression_type="lz4",
        )

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)

        # Verify Producer was called with expected config
        call_args = mock_producer_class.call_args[0][0]
        assert call_args["bootstrap.servers"] == "broker1:9092,broker2:9092"
        assert call_args["acks"] == "all"
        assert call_args["retries"] == 5

        # Cleanup
        UpbitKafkaProducer._instance = None

    @patch("src.producers.kafka_producer.Producer")
    def test_producer_singleton_pattern(self, mock_producer_class):
        """Test producer follows singleton pattern."""
        UpbitKafkaProducer._instance = None

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer1 = UpbitKafkaProducer(config)
            producer2 = UpbitKafkaProducer(config)

        assert producer1 is producer2
        # Producer should only be created once
        assert mock_producer_class.call_count == 1

        UpbitKafkaProducer._instance = None


# =============================================================================
# Message Production Tests
# =============================================================================


class TestMessageProduction:
    """Tests for message production."""

    @patch("src.producers.kafka_producer.Producer")
    def test_produce_ticker(self, mock_producer_class, sample_ticker_message):
        """Test producing ticker message."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig(topic_ticker="upbit-ticker")

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            producer.produce_ticker(sample_ticker_message)

        # Verify produce was called
        mock_producer.produce.assert_called_once()
        call_kwargs = mock_producer.produce.call_args[1]

        assert call_kwargs["topic"] == "upbit-ticker"
        assert call_kwargs["key"] == b"KRW-BTC"
        assert ("type", b"ticker") in call_kwargs["headers"]

        UpbitKafkaProducer._instance = None

    @patch("src.producers.kafka_producer.Producer")
    def test_produce_trade(self, mock_producer_class, sample_trade_message):
        """Test producing trade message."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig(topic_trade="upbit-trade")

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            producer.produce_trade(sample_trade_message)

        call_kwargs = mock_producer.produce.call_args[1]
        assert call_kwargs["topic"] == "upbit-trade"
        assert ("type", b"trade") in call_kwargs["headers"]

        UpbitKafkaProducer._instance = None

    @patch("src.producers.kafka_producer.Producer")
    def test_produce_orderbook(self, mock_producer_class, sample_orderbook_message):
        """Test producing orderbook message."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig(topic_orderbook="upbit-orderbook")

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            producer.produce_orderbook(sample_orderbook_message)

        call_kwargs = mock_producer.produce.call_args[1]
        assert call_kwargs["topic"] == "upbit-orderbook"
        assert ("type", b"orderbook") in call_kwargs["headers"]

        UpbitKafkaProducer._instance = None

    @patch("src.producers.kafka_producer.Producer")
    def test_produce_with_custom_key(self, mock_producer_class):
        """Test producing with custom key."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            producer.produce(
                topic="test-topic",
                value={"data": "test"},
                key="custom-key",
            )

        call_kwargs = mock_producer.produce.call_args[1]
        assert call_kwargs["key"] == b"custom-key"

        UpbitKafkaProducer._instance = None

    @patch("src.producers.kafka_producer.Producer")
    def test_produce_without_key(self, mock_producer_class):
        """Test producing without key."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            producer.produce(
                topic="test-topic",
                value={"data": "test"},
            )

        call_kwargs = mock_producer.produce.call_args[1]
        assert call_kwargs["key"] is None

        UpbitKafkaProducer._instance = None


# =============================================================================
# Delivery Callback Tests
# =============================================================================


class TestDeliveryCallbacks:
    """Tests for delivery callback handling."""

    @patch("src.producers.kafka_producer.Producer")
    def test_delivery_callback_success(self, mock_producer_class):
        """Test delivery callback on successful delivery."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)

            # Simulate successful delivery
            mock_msg = Mock()
            mock_msg.topic.return_value = "test-topic"
            mock_msg.partition.return_value = 0

            producer._delivery_callback(None, mock_msg)

        assert producer._delivery_count == 1
        assert producer._error_count == 0

        UpbitKafkaProducer._instance = None

    @patch("src.producers.kafka_producer.Producer")
    def test_delivery_callback_error(self, mock_producer_class):
        """Test delivery callback on delivery failure."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)

            # Simulate failed delivery
            mock_msg = Mock()
            mock_msg.topic.return_value = "test-topic"
            mock_msg.partition.return_value = 0

            producer._delivery_callback("Connection error", mock_msg)

        assert producer._delivery_count == 0
        assert producer._error_count == 1

        UpbitKafkaProducer._instance = None


# =============================================================================
# Buffer and Flush Tests
# =============================================================================


class TestBufferAndFlush:
    """Tests for buffer handling and flush operations."""

    @patch("src.producers.kafka_producer.Producer")
    def test_flush_returns_remaining(self, mock_producer_class):
        """Test flush returns number of remaining messages."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer.flush.return_value = 0
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            remaining = producer.flush(timeout=5.0)

        assert remaining == 0
        mock_producer.flush.assert_called_once_with(5.0)

        UpbitKafkaProducer._instance = None

    @patch("src.producers.kafka_producer.Producer")
    def test_buffer_full_handling(self, mock_producer_class):
        """Test handling of buffer full error."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()

        # First call raises BufferError, second succeeds
        mock_producer.produce.side_effect = [BufferError("Buffer full"), None]
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            producer.produce(topic="test-topic", value={"data": "test"})

        # Should have called poll and retried
        mock_producer.poll.assert_called()
        assert mock_producer.produce.call_count == 2

        UpbitKafkaProducer._instance = None


# =============================================================================
# Statistics Tests
# =============================================================================


class TestProducerStats:
    """Tests for producer statistics."""

    @patch("src.producers.kafka_producer.Producer")
    def test_stats_tracking(self, mock_producer_class):
        """Test statistics are tracked correctly."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)

            # Simulate some deliveries
            mock_msg = Mock()
            mock_msg.topic.return_value = "test"
            mock_msg.partition.return_value = 0

            for _ in range(5):
                producer._delivery_callback(None, mock_msg)
            for _ in range(2):
                producer._delivery_callback("error", mock_msg)

            stats = producer.stats

        assert stats["delivered"] == 5
        assert stats["errors"] == 2

        UpbitKafkaProducer._instance = None


# =============================================================================
# Topic Creation Tests
# =============================================================================


class TestTopicCreation:
    """Tests for topic creation utility."""

    @patch("src.producers.kafka_producer.AdminClient")
    @patch("src.producers.kafka_producer.get_config")
    def test_ensure_topics_exist_creates_missing(
        self, mock_get_config, mock_admin_class
    ):
        """Test that missing topics are created."""
        mock_config = Mock()
        mock_config.kafka.bootstrap_servers = "localhost:9092"
        mock_get_config.return_value = mock_config

        mock_admin = MagicMock()
        mock_admin.list_topics.return_value.topics = {"existing-topic": Mock()}
        mock_admin.create_topics.return_value = {"new-topic": Mock()}
        mock_admin_class.return_value = mock_admin

        ensure_topics_exist(["existing-topic", "new-topic"])

        # Should only create the new topic
        mock_admin.create_topics.assert_called_once()
        created_topics = mock_admin.create_topics.call_args[0][0]
        assert len(created_topics) == 1
        assert created_topics[0].topic == "new-topic"

    @patch("src.producers.kafka_producer.AdminClient")
    @patch("src.producers.kafka_producer.get_config")
    def test_ensure_topics_exist_all_exist(
        self, mock_get_config, mock_admin_class
    ):
        """Test no creation when all topics exist."""
        mock_config = Mock()
        mock_config.kafka.bootstrap_servers = "localhost:9092"
        mock_get_config.return_value = mock_config

        mock_admin = MagicMock()
        mock_admin.list_topics.return_value.topics = {
            "topic1": Mock(),
            "topic2": Mock(),
        }
        mock_admin_class.return_value = mock_admin

        ensure_topics_exist(["topic1", "topic2"])

        # Should not create any topics
        mock_admin.create_topics.assert_not_called()


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestProducerCleanup:
    """Tests for producer cleanup and shutdown."""

    @patch("src.producers.kafka_producer.Producer")
    def test_close_flushes_messages(self, mock_producer_class):
        """Test close flushes pending messages."""
        UpbitKafkaProducer._instance = None
        mock_producer = MagicMock()
        mock_producer.flush.return_value = 0
        mock_producer_class.return_value = mock_producer

        config = KafkaConfig()

        with patch("src.producers.kafka_producer.get_config") as mock_get_config:
            mock_get_config.return_value.kafka = config
            producer = UpbitKafkaProducer(config)
            producer.close()

        mock_producer.flush.assert_called_with(30.0)

        UpbitKafkaProducer._instance = None
