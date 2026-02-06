"""
Tests for Upbit WebSocket client.

Uses mocking to test WebSocket behavior without requiring
an actual connection to Upbit servers.
"""
import asyncio
import json
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from src.consumers.upbit_websocket import (
    UpbitWebSocketClient,
    Subscription,
    SubscriptionType,
    MessageHandler,
)
from src.models import TickerMessage, TradeMessage, OrderbookMessage
from src.config import UpbitConfig


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def upbit_config():
    """Test Upbit configuration."""
    return UpbitConfig(
        websocket_url="wss://api.upbit.com/websocket/v1",
        ping_interval=30,
        ping_timeout=10,
        reconnect_delay=1,
        max_reconnect_attempts=3,
    )


@pytest.fixture
def mock_handler():
    """Mock message handler."""
    handler = MagicMock(spec=MessageHandler)
    handler.handle_ticker = AsyncMock()
    handler.handle_trade = AsyncMock()
    handler.handle_orderbook = AsyncMock()
    return handler


@pytest.fixture
def sample_ticker_ws_message():
    """Sample ticker WebSocket message as bytes."""
    data = {
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
        "acc_trade_price": 50000000000.0,
        "trade_date": "20240215",
        "trade_time": "120000",
        "trade_timestamp": 1707984000000,
        "ask_bid": "BID",
        "highest_52_week_price": 75000000.0,
        "highest_52_week_date": "2024-01-15",
        "lowest_52_week_price": 35000000.0,
        "lowest_52_week_date": "2023-06-15",
        "timestamp": 1707984000123,
    }
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def sample_trade_ws_message():
    """Sample trade WebSocket message as bytes."""
    data = {
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
    }
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def sample_orderbook_ws_message():
    """Sample orderbook WebSocket message as bytes."""
    data = {
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
            }
        ],
    }
    return json.dumps(data).encode("utf-8")


# =============================================================================
# Subscription Tests
# =============================================================================


class TestSubscription:
    """Tests for Subscription class."""

    def test_subscription_to_dict(self):
        """Test subscription serialization to dict."""
        sub = Subscription(
            type=SubscriptionType.TICKER,
            codes=["KRW-BTC", "KRW-ETH"],
            is_only_realtime=True,
        )

        result = sub.to_dict()

        assert result["type"] == "ticker"
        assert result["codes"] == ["KRW-BTC", "KRW-ETH"]
        assert result["is_only_realtime"] is True

    def test_subscription_snapshot_only(self):
        """Test snapshot-only subscription."""
        sub = Subscription(
            type=SubscriptionType.ORDERBOOK,
            codes=["KRW-BTC"],
            is_only_realtime=False,
            is_only_snapshot=True,
        )

        result = sub.to_dict()

        assert "is_only_realtime" not in result
        assert result["is_only_snapshot"] is True


# =============================================================================
# Client Initialization Tests
# =============================================================================


class TestClientInitialization:
    """Tests for WebSocket client initialization."""

    def test_client_initialization(self, mock_handler, upbit_config):
        """Test client is initialized correctly."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        assert client._config == upbit_config
        assert client._handler == mock_handler
        assert client._subscriptions == []
        assert client._message_count == 0

    def test_subscribe_ticker(self, mock_handler, upbit_config):
        """Test ticker subscription."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        client.subscribe_ticker(["KRW-BTC", "KRW-ETH"])

        assert len(client._subscriptions) == 1
        assert client._subscriptions[0].type == SubscriptionType.TICKER
        assert "KRW-BTC" in client._connected_markets
        assert "KRW-ETH" in client._connected_markets

    def test_subscribe_trade(self, mock_handler, upbit_config):
        """Test trade subscription."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        client.subscribe_trade(["KRW-BTC"])

        assert len(client._subscriptions) == 1
        assert client._subscriptions[0].type == SubscriptionType.TRADE

    def test_subscribe_orderbook(self, mock_handler, upbit_config):
        """Test orderbook subscription."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        client.subscribe_orderbook(["KRW-BTC"])

        assert len(client._subscriptions) == 1
        assert client._subscriptions[0].type == SubscriptionType.ORDERBOOK

    def test_multiple_subscriptions(self, mock_handler, upbit_config):
        """Test multiple subscription types."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        client.subscribe_ticker(["KRW-BTC"])
        client.subscribe_trade(["KRW-BTC"])
        client.subscribe_orderbook(["KRW-BTC"])

        assert len(client._subscriptions) == 3


# =============================================================================
# Message Building Tests
# =============================================================================


class TestMessageBuilding:
    """Tests for WebSocket message construction."""

    def test_build_subscribe_message(self, mock_handler, upbit_config):
        """Test subscription message building."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )
        client.subscribe_ticker(["KRW-BTC", "KRW-ETH"])

        message = client._build_subscribe_message()
        parsed = json.loads(message)

        # Should have ticket, subscription, and format
        assert len(parsed) == 3
        assert "ticket" in parsed[0]
        assert parsed[1]["type"] == "ticker"
        assert parsed[1]["codes"] == ["KRW-BTC", "KRW-ETH"]
        assert parsed[2]["format"] == "DEFAULT"


# =============================================================================
# Message Handling Tests
# =============================================================================


class TestMessageHandling:
    """Tests for message handling."""

    @pytest.mark.asyncio
    async def test_handle_ticker_message(
        self, mock_handler, upbit_config, sample_ticker_ws_message
    ):
        """Test ticker message handling."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        await client._handle_message(sample_ticker_ws_message)

        mock_handler.handle_ticker.assert_called_once()
        call_args = mock_handler.handle_ticker.call_args[0][0]
        assert isinstance(call_args, TickerMessage)
        assert call_args.market == "KRW-BTC"

    @pytest.mark.asyncio
    async def test_handle_trade_message(
        self, mock_handler, upbit_config, sample_trade_ws_message
    ):
        """Test trade message handling."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        await client._handle_message(sample_trade_ws_message)

        mock_handler.handle_trade.assert_called_once()
        call_args = mock_handler.handle_trade.call_args[0][0]
        assert isinstance(call_args, TradeMessage)
        assert call_args.market == "KRW-BTC"

    @pytest.mark.asyncio
    async def test_handle_orderbook_message(
        self, mock_handler, upbit_config, sample_orderbook_ws_message
    ):
        """Test orderbook message handling."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        await client._handle_message(sample_orderbook_ws_message)

        mock_handler.handle_orderbook.assert_called_once()
        call_args = mock_handler.handle_orderbook.call_args[0][0]
        assert isinstance(call_args, OrderbookMessage)
        assert call_args.market == "KRW-BTC"

    @pytest.mark.asyncio
    async def test_handle_string_message(self, mock_handler, upbit_config):
        """Test handling of string (not bytes) message."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        message = json.dumps({
            "type": "ticker",
            "market": "KRW-ETH",
            "trade_price": 3000000.0,
            "opening_price": 2900000.0,
            "high_price": 3100000.0,
            "low_price": 2800000.0,
            "prev_closing_price": 2900000.0,
            "change": "RISE",
            "trade_timestamp": 1707984000000,
            "timestamp": 1707984000123,
        })

        await client._handle_message(message)

        mock_handler.handle_ticker.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_status_message(self, mock_handler, upbit_config):
        """Test status message is ignored."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        message = json.dumps({"status": "UP"}).encode("utf-8")
        await client._handle_message(message)

        # Should not call any handler
        mock_handler.handle_ticker.assert_not_called()
        mock_handler.handle_trade.assert_not_called()
        mock_handler.handle_orderbook.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_error_message(self, mock_handler, upbit_config):
        """Test error message is logged but not processed."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        message = json.dumps({
            "error": {"name": "BAD_REQUEST", "message": "Invalid request"}
        }).encode("utf-8")

        await client._handle_message(message)

        # Should not call any handler
        mock_handler.handle_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, mock_handler, upbit_config):
        """Test invalid JSON is handled gracefully."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        # Should not raise exception
        await client._handle_message(b"invalid json {{{")

        # Should not call any handler
        mock_handler.handle_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_unknown_type(self, mock_handler, upbit_config):
        """Test unknown message type is skipped."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        message = json.dumps({"type": "unknown", "data": "test"}).encode("utf-8")
        await client._handle_message(message)

        # Should not call any handler
        mock_handler.handle_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_count_increments(
        self, mock_handler, upbit_config, sample_ticker_ws_message
    ):
        """Test message count increments on successful handling."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        assert client._message_count == 0

        await client._handle_message(sample_ticker_ws_message)
        assert client._message_count == 1

        await client._handle_message(sample_ticker_ws_message)
        assert client._message_count == 2


# =============================================================================
# Reconnection Tests
# =============================================================================


class TestReconnection:
    """Tests for reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_with_backoff(self, mock_handler, upbit_config):
        """Test exponential backoff on reconnection."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        with patch.object(client, "_connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = [Exception("Connection failed"), None]

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await client._reconnect_with_backoff()

        assert result is True
        mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_max_reconnect_attempts(self, mock_handler, upbit_config):
        """Test max reconnection attempts are respected."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )
        client._reconnect_count = upbit_config.max_reconnect_attempts

        result = await client._reconnect_with_backoff()

        assert result is False


# =============================================================================
# Client State Tests
# =============================================================================


class TestClientState:
    """Tests for client state properties."""

    def test_is_connected_false_initially(self, mock_handler, upbit_config):
        """Test is_connected is False when not connected."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        assert client.is_connected is False

    def test_stats_property(self, mock_handler, upbit_config):
        """Test stats property returns correct data."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )
        client.subscribe_ticker(["KRW-BTC", "KRW-ETH"])
        client._message_count = 100
        client._reconnect_count = 2

        stats = client.stats

        assert stats["message_count"] == 100
        assert stats["reconnect_count"] == 2
        assert stats["connected_markets"] == 2
        assert stats["is_connected"] is False


# =============================================================================
# Graceful Shutdown Tests
# =============================================================================


class TestGracefulShutdown:
    """Tests for graceful shutdown."""

    @pytest.mark.asyncio
    async def test_stop_sets_shutdown_event(self, mock_handler, upbit_config):
        """Test stop sets shutdown event."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        assert not client._shutdown_event.is_set()

        await client.stop()

        assert client._shutdown_event.is_set()
        assert client._running is False

    @pytest.mark.asyncio
    async def test_stop_closes_websocket(self, mock_handler, upbit_config):
        """Test stop closes WebSocket connection."""
        client = UpbitWebSocketClient(
            handler=mock_handler,
            config=upbit_config,
        )

        mock_ws = AsyncMock()
        client._websocket = mock_ws

        await client.stop()

        mock_ws.close.assert_called_once()
