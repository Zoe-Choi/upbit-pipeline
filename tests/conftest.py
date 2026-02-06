"""
Pytest configuration and shared fixtures.

This module provides common fixtures used across all test modules.
Fixtures are organized by category for easy discovery.
"""
import pytest
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, AsyncMock


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_ticker_data() -> Dict[str, Any]:
    """
    Complete ticker WebSocket message.
    
    Contains all fields from a real Upbit ticker message.
    """
    return {
        "type": "ticker",
        "market": "KRW-BTC",
        "trade_price": 50000000.0,
        "opening_price": 49500000.0,
        "high_price": 50500000.0,
        "low_price": 49000000.0,
        "prev_closing_price": 49500000.0,
        "change": "RISE",
        "change_price": 500000.0,
        "change_rate": 0.0101,
        "signed_change_price": 500000.0,
        "signed_change_rate": 0.0101,
        "trade_volume": 0.5,
        "acc_trade_volume": 1000.0,
        "acc_trade_volume_24h": 2500.0,
        "acc_trade_price": 50000000000.0,
        "acc_trade_price_24h": 125000000000.0,
        "trade_date": "20240215",
        "trade_time": "120000",
        "trade_timestamp": 1707984000000,
        "ask_bid": "BID",
        "highest_52_week_price": 75000000.0,
        "highest_52_week_date": "2024-01-15",
        "lowest_52_week_price": 35000000.0,
        "lowest_52_week_date": "2023-06-15",
        "timestamp": 1707984000123,
        "stream_type": "REALTIME",
        "acc_ask_volume": 400.0,
        "acc_bid_volume": 600.0,
        "market_state": "ACTIVE",
        "market_warning": "NONE",
    }


@pytest.fixture
def sample_trade_data() -> Dict[str, Any]:
    """
    Complete trade WebSocket message.
    
    Contains all fields from a real Upbit trade message.
    """
    return {
        "type": "trade",
        "market": "KRW-BTC",
        "trade_price": 50000000.0,
        "trade_volume": 0.1,
        "ask_bid": "BID",
        "trade_date": "20240215",
        "trade_time": "120000",
        "trade_timestamp": 1707984000000,
        "timestamp": 1707984000123,
        "prev_closing_price": 49500000.0,
        "change": "RISE",
        "change_price": 500000.0,
        "sequential_id": 1707984000000001,
        "stream_type": "REALTIME",
    }


@pytest.fixture
def sample_orderbook_data() -> Dict[str, Any]:
    """
    Complete orderbook WebSocket message.
    
    Contains orderbook with multiple price levels.
    """
    return {
        "type": "orderbook",
        "market": "KRW-BTC",
        "timestamp": 1707984000123,
        "total_ask_size": 100.0,
        "total_bid_size": 150.0,
        "orderbook_units": [
            {
                "ask_price": 50010000.0,
                "bid_price": 50000000.0,
                "ask_size": 1.5,
                "bid_size": 2.0,
            },
            {
                "ask_price": 50020000.0,
                "bid_price": 49990000.0,
                "ask_size": 2.0,
                "bid_size": 3.0,
            },
            {
                "ask_price": 50030000.0,
                "bid_price": 49980000.0,
                "ask_size": 2.5,
                "bid_size": 3.5,
            },
        ],
        "stream_type": "REALTIME",
        "level": 0,
    }


# =============================================================================
# Minimal Data Fixtures (for testing required fields)
# =============================================================================


@pytest.fixture
def minimal_ticker_data() -> Dict[str, Any]:
    """Minimal ticker data with only required fields."""
    return {
        "market": "KRW-BTC",
        "trade_price": 50000000.0,
        "opening_price": 49500000.0,
        "high_price": 50500000.0,
        "low_price": 49000000.0,
        "prev_closing_price": 49500000.0,
        "change": "RISE",
        "trade_timestamp": 1707984000000,
        "timestamp": 1707984000123,
    }


@pytest.fixture
def minimal_trade_data() -> Dict[str, Any]:
    """Minimal trade data with only required fields."""
    return {
        "market": "KRW-BTC",
        "trade_price": 50000000.0,
        "trade_volume": 0.1,
        "ask_bid": "BID",
        "trade_timestamp": 1707984000000,
        "timestamp": 1707984000123,
        "sequential_id": 1707984000000001,
    }


@pytest.fixture
def minimal_orderbook_data() -> Dict[str, Any]:
    """Minimal orderbook data with only required fields."""
    return {
        "market": "KRW-BTC",
        "timestamp": 1707984000123,
        "total_ask_size": 100.0,
        "total_bid_size": 150.0,
    }


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer."""
    producer = MagicMock()
    producer.produce = MagicMock()
    producer.poll = MagicMock(return_value=0)
    producer.flush = MagicMock(return_value=0)
    return producer


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    ws.open = True
    return ws


@pytest.fixture
def mock_message_handler():
    """Mock message handler."""
    from src.consumers.upbit_websocket import MessageHandler
    
    handler = MagicMock(spec=MessageHandler)
    handler.handle_ticker = AsyncMock()
    handler.handle_trade = AsyncMock()
    handler.handle_orderbook = AsyncMock()
    return handler


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def test_kafka_config():
    """Test Kafka configuration."""
    from src.config import KafkaConfig
    
    return KafkaConfig(
        bootstrap_servers="localhost:9092",
        topic_ticker="test-ticker",
        topic_trade="test-trade",
        topic_orderbook="test-orderbook",
    )


@pytest.fixture
def test_upbit_config():
    """Test Upbit configuration."""
    from src.config import UpbitConfig
    
    return UpbitConfig(
        websocket_url="wss://api.upbit.com/websocket/v1",
        ping_interval=30,
        ping_timeout=10,
        reconnect_delay=1,
        max_reconnect_attempts=3,
    )


# =============================================================================
# Parametrized Data Fixtures
# =============================================================================


@pytest.fixture(params=["KRW-BTC", "KRW-ETH", "KRW-SOL"])
def market_code(request) -> str:
    """Parametrized market codes for testing multiple markets."""
    return request.param


@pytest.fixture(params=["RISE", "FALL", "EVEN"])
def change_type(request) -> str:
    """Parametrized change types."""
    return request.param


@pytest.fixture(params=["ASK", "BID"])
def ask_bid_type(request) -> str:
    """Parametrized ask/bid types."""
    return request.param


# =============================================================================
# Cleanup Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    yield
    
    # Reset UpbitKafkaProducer singleton
    from src.producers.kafka_producer import UpbitKafkaProducer
    UpbitKafkaProducer._instance = None


# =============================================================================
# Async Event Loop Configuration
# =============================================================================


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
