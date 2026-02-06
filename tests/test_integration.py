"""
Integration tests for the Upbit data pipeline.

These tests verify that components work together correctly.
They use mocks for external dependencies (Kafka, WebSocket)
but test real interactions between internal components.
"""
import asyncio
import json
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import List, Dict, Any

from src.models import TickerMessage, TradeMessage, OrderbookMessage
from src.pipeline.kafka_handler import KafkaMessageHandler
from src.consumers.upbit_websocket import UpbitWebSocketClient
from src.config import get_config


# =============================================================================
# End-to-End Message Flow Tests
# =============================================================================


class TestMessageFlow:
    """Tests for complete message flow from WebSocket to Kafka."""

    @pytest.mark.asyncio
    async def test_ticker_flow_websocket_to_handler(
        self, sample_ticker_data, mock_kafka_producer
    ):
        """Test ticker message flows from parsing to handler."""
        # Create message from WebSocket data
        ticker = TickerMessage.from_websocket(sample_ticker_data)
        
        # Verify message properties
        assert ticker.market == "KRW-BTC"
        assert ticker.trade_price == 50000000.0
        
        # Convert to Kafka format
        kafka_msg = ticker.to_kafka_message()
        
        # Verify Kafka message structure
        assert "_metadata" in kafka_msg
        assert kafka_msg["market"] == "KRW-BTC"
        assert kafka_msg["_metadata"]["source"] == "upbit_websocket"

    @pytest.mark.asyncio
    async def test_trade_flow_websocket_to_handler(
        self, sample_trade_data, mock_kafka_producer
    ):
        """Test trade message flows from parsing to handler."""
        trade = TradeMessage.from_websocket(sample_trade_data)
        
        assert trade.market == "KRW-BTC"
        assert trade.trade_value == 50000000.0 * 0.1
        
        kafka_msg = trade.to_kafka_message()
        assert kafka_msg["market"] == "KRW-BTC"

    @pytest.mark.asyncio
    async def test_orderbook_flow_websocket_to_handler(
        self, sample_orderbook_data, mock_kafka_producer
    ):
        """Test orderbook message flows from parsing to handler."""
        orderbook = OrderbookMessage.from_websocket(sample_orderbook_data)
        
        assert orderbook.market == "KRW-BTC"
        assert orderbook.depth == 3
        assert orderbook.spread == 10000.0
        
        kafka_msg = orderbook.to_kafka_message()
        assert "spread" in kafka_msg
        assert "imbalance" in kafka_msg


class TestKafkaHandlerIntegration:
    """Tests for KafkaMessageHandler integration."""

    @pytest.mark.asyncio
    async def test_handler_processes_ticker(self, sample_ticker_data):
        """Test handler processes ticker message correctly."""
        with patch("src.pipeline.kafka_handler.UpbitKafkaProducer") as MockProducer:
            mock_producer = MagicMock()
            MockProducer.return_value = mock_producer
            
            handler = KafkaMessageHandler()
            ticker = TickerMessage.from_websocket(sample_ticker_data)
            
            await handler.handle_ticker(ticker)
            
            assert handler._ticker_count == 1

    @pytest.mark.asyncio
    async def test_handler_processes_trade(self, sample_trade_data):
        """Test handler processes trade message correctly."""
        with patch("src.pipeline.kafka_handler.UpbitKafkaProducer") as MockProducer:
            mock_producer = MagicMock()
            MockProducer.return_value = mock_producer
            
            handler = KafkaMessageHandler()
            trade = TradeMessage.from_websocket(sample_trade_data)
            
            await handler.handle_trade(trade)
            
            assert handler._trade_count == 1

    @pytest.mark.asyncio
    async def test_handler_stats(self, sample_ticker_data, sample_trade_data):
        """Test handler statistics are tracked correctly."""
        with patch("src.pipeline.kafka_handler.UpbitKafkaProducer") as MockProducer:
            mock_producer = MagicMock()
            mock_producer.stats = {"delivered": 0, "errors": 0}
            MockProducer.return_value = mock_producer
            
            handler = KafkaMessageHandler()
            
            ticker = TickerMessage.from_websocket(sample_ticker_data)
            trade = TradeMessage.from_websocket(sample_trade_data)
            
            await handler.handle_ticker(ticker)
            await handler.handle_ticker(ticker)
            await handler.handle_trade(trade)
            
            stats = handler.stats
            
            assert stats["ticker_count"] == 2
            assert stats["trade_count"] == 1
            assert stats["orderbook_count"] == 0


class TestWebSocketClientIntegration:
    """Tests for WebSocket client integration with handler."""

    @pytest.mark.asyncio
    async def test_client_routes_messages_to_handler(
        self,
        sample_ticker_data,
        sample_trade_data,
        sample_orderbook_data,
        mock_message_handler,
        test_upbit_config,
    ):
        """Test client routes different message types to correct handlers."""
        client = UpbitWebSocketClient(
            handler=mock_message_handler,
            config=test_upbit_config,
        )
        
        # Process different message types
        await client._handle_message(json.dumps(sample_ticker_data).encode())
        await client._handle_message(json.dumps(sample_trade_data).encode())
        await client._handle_message(json.dumps(sample_orderbook_data).encode())
        
        # Verify each handler was called once
        mock_message_handler.handle_ticker.assert_called_once()
        mock_message_handler.handle_trade.assert_called_once()
        mock_message_handler.handle_orderbook.assert_called_once()
        
        # Verify message count
        assert client._message_count == 3

    @pytest.mark.asyncio
    async def test_client_handles_burst_of_messages(
        self,
        sample_ticker_data,
        mock_message_handler,
        test_upbit_config,
    ):
        """Test client handles burst of messages correctly."""
        client = UpbitWebSocketClient(
            handler=mock_message_handler,
            config=test_upbit_config,
        )
        
        # Simulate burst of messages
        for i in range(100):
            data = sample_ticker_data.copy()
            data["trade_price"] = 50000000.0 + i * 1000
            await client._handle_message(json.dumps(data).encode())
        
        assert client._message_count == 100
        assert mock_message_handler.handle_ticker.call_count == 100


# =============================================================================
# Data Consistency Tests
# =============================================================================


class TestDataConsistency:
    """Tests for data consistency across transformations."""

    def test_ticker_roundtrip_consistency(self, sample_ticker_data):
        """Test ticker data is consistent through transformations."""
        # Create from WebSocket
        ticker = TickerMessage.from_websocket(sample_ticker_data)
        
        # Convert to Kafka message
        kafka_msg = ticker.to_kafka_message()
        
        # Verify key fields are preserved
        assert kafka_msg["market"] == sample_ticker_data["market"]
        assert kafka_msg["trade_price"] == sample_ticker_data["trade_price"]
        assert kafka_msg["change"] == sample_ticker_data["change"]
        assert kafka_msg["timestamp"] == sample_ticker_data["timestamp"]

    def test_trade_roundtrip_consistency(self, sample_trade_data):
        """Test trade data is consistent through transformations."""
        trade = TradeMessage.from_websocket(sample_trade_data)
        kafka_msg = trade.to_kafka_message()
        
        assert kafka_msg["market"] == sample_trade_data["market"]
        assert kafka_msg["trade_price"] == sample_trade_data["trade_price"]
        assert kafka_msg["trade_volume"] == sample_trade_data["trade_volume"]
        assert kafka_msg["sequential_id"] == sample_trade_data["sequential_id"]

    def test_orderbook_roundtrip_consistency(self, sample_orderbook_data):
        """Test orderbook data is consistent through transformations."""
        orderbook = OrderbookMessage.from_websocket(sample_orderbook_data)
        kafka_msg = orderbook.to_kafka_message()
        
        assert kafka_msg["market"] == sample_orderbook_data["market"]
        assert kafka_msg["total_ask_size"] == sample_orderbook_data["total_ask_size"]
        assert kafka_msg["total_bid_size"] == sample_orderbook_data["total_bid_size"]
        assert len(kafka_msg["orderbook_units"]) == len(
            sample_orderbook_data["orderbook_units"]
        )


# =============================================================================
# Multi-Market Tests
# =============================================================================


class TestMultiMarket:
    """Tests for handling multiple markets simultaneously."""

    @pytest.mark.asyncio
    async def test_handle_multiple_markets(
        self, mock_message_handler, test_upbit_config
    ):
        """Test handling messages from multiple markets."""
        client = UpbitWebSocketClient(
            handler=mock_message_handler,
            config=test_upbit_config,
        )
        
        markets = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]
        
        for market in markets:
            data = {
                "type": "ticker",
                "market": market,
                "trade_price": 50000000.0,
                "opening_price": 49500000.0,
                "high_price": 50500000.0,
                "low_price": 49000000.0,
                "prev_closing_price": 49500000.0,
                "change": "RISE",
                "trade_timestamp": 1707984000000,
                "timestamp": 1707984000123,
            }
            await client._handle_message(json.dumps(data).encode())
        
        assert mock_message_handler.handle_ticker.call_count == 3
        
        # Verify each market was processed
        calls = mock_message_handler.handle_ticker.call_args_list
        processed_markets = [call[0][0].market for call in calls]
        assert set(processed_markets) == set(markets)

    def test_create_messages_for_multiple_markets(self, market_code):
        """Parametrized test for multiple market codes."""
        data = {
            "market": market_code,
            "trade_price": 50000000.0,
            "opening_price": 49500000.0,
            "high_price": 50500000.0,
            "low_price": 49000000.0,
            "prev_closing_price": 49500000.0,
            "change": "RISE",
            "trade_timestamp": 1707984000000,
            "timestamp": 1707984000123,
        }
        
        ticker = TickerMessage.from_websocket(data)
        assert ticker.market == market_code
        assert ticker.symbol == market_code.split("-")[1]


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestErrorRecovery:
    """Tests for error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_handler_continues_after_error(
        self, sample_ticker_data, mock_message_handler, test_upbit_config
    ):
        """Test client continues processing after handler error."""
        # Make handler raise error on first call
        mock_message_handler.handle_ticker.side_effect = [
            Exception("Handler error"),
            None,
            None,
        ]
        
        client = UpbitWebSocketClient(
            handler=mock_message_handler,
            config=test_upbit_config,
        )
        
        # Process multiple messages - should continue after error
        for _ in range(3):
            await client._handle_message(json.dumps(sample_ticker_data).encode())
        
        # All messages should have been attempted
        assert mock_message_handler.handle_ticker.call_count == 3

    @pytest.mark.asyncio
    async def test_invalid_message_doesnt_break_flow(
        self, sample_ticker_data, mock_message_handler, test_upbit_config
    ):
        """Test invalid messages don't break the flow."""
        client = UpbitWebSocketClient(
            handler=mock_message_handler,
            config=test_upbit_config,
        )
        
        # Send invalid, valid, invalid, valid
        await client._handle_message(b"invalid json")
        await client._handle_message(json.dumps(sample_ticker_data).encode())
        await client._handle_message(b"")
        await client._handle_message(json.dumps(sample_ticker_data).encode())
        
        # Only valid messages should be processed
        assert mock_message_handler.handle_ticker.call_count == 2


# =============================================================================
# Configuration Integration Tests
# =============================================================================


class TestConfigurationIntegration:
    """Tests for configuration integration."""

    def test_config_provides_valid_settings(self):
        """Test configuration provides valid settings."""
        # This will use real configuration loading
        # but with default values
        config = get_config()
        
        assert config.upbit.websocket_url.startswith("wss://")
        assert config.kafka.bootstrap_servers
        assert len(config.markets.default_markets) > 0

    def test_markets_config_has_expected_pairs(self):
        """Test markets configuration has expected trading pairs."""
        config = get_config()
        markets = config.markets.default_markets
        
        # Should include major pairs
        assert "KRW-BTC" in markets
        assert "KRW-ETH" in markets
        assert "KRW-SOL" in markets
