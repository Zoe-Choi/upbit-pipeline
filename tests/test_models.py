"""
Tests for data models.

Comprehensive tests covering:
- Model instantiation from WebSocket data
- Data validation and error handling
- Property calculations
- Serialization to dict/JSON/Kafka formats
"""
import json
import pytest
from datetime import datetime, timezone

from src.models import (
    TickerMessage,
    TradeMessage,
    OrderbookMessage,
    OrderbookUnit,
    ChangeType,
    AskBid,
    StreamType,
    MessageValidator,
)
from src.exceptions import MissingFieldError, InvalidTypeError, InvalidValueError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_ticker_data():
    """Minimal valid ticker data."""
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
def full_ticker_data():
    """Complete ticker data with all fields."""
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
def trade_data():
    """Valid trade data."""
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
def orderbook_data():
    """Valid orderbook data."""
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
        ],
        "stream_type": "REALTIME",
        "level": 0,
    }


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum classes."""

    def test_change_type_from_valid_value(self):
        """Test ChangeType creation from valid string."""
        assert ChangeType.from_value("RISE") == ChangeType.RISE
        assert ChangeType.from_value("rise") == ChangeType.RISE
        assert ChangeType.from_value("FALL") == ChangeType.FALL

    def test_change_type_fallback_to_even(self):
        """Test ChangeType fallback for invalid values."""
        assert ChangeType.from_value("INVALID") == ChangeType.EVEN
        assert ChangeType.from_value("") == ChangeType.EVEN
        assert ChangeType.from_value(None) == ChangeType.EVEN

    def test_ask_bid_properties(self):
        """Test AskBid properties."""
        assert AskBid.BID.is_buy is True
        assert AskBid.BID.is_sell is False
        assert AskBid.ASK.is_buy is False
        assert AskBid.ASK.is_sell is True

    def test_stream_type_fallback(self):
        """Test StreamType fallback for invalid values."""
        assert StreamType.from_value("INVALID") == StreamType.REALTIME


# =============================================================================
# MessageValidator Tests
# =============================================================================


class TestMessageValidator:
    """Tests for MessageValidator utility class."""

    def test_validate_positive_with_valid_value(self):
        """Test positive validation passes for positive values."""
        assert MessageValidator.validate_positive(100.0, "price") == 100.0
        assert MessageValidator.validate_positive(0.0, "price") == 0.0

    def test_validate_positive_with_negative_value(self):
        """Test positive validation fails for negative values."""
        with pytest.raises(InvalidValueError) as exc_info:
            MessageValidator.validate_positive(-100.0, "price")
        assert "price" in str(exc_info.value)
        assert "positive" in str(exc_info.value)

    def test_validate_not_empty_with_valid_value(self):
        """Test not empty validation passes for non-empty strings."""
        assert MessageValidator.validate_not_empty("BTC", "symbol") == "BTC"

    def test_validate_not_empty_with_empty_value(self):
        """Test not empty validation fails for empty strings."""
        with pytest.raises(InvalidValueError):
            MessageValidator.validate_not_empty("", "symbol")
        with pytest.raises(InvalidValueError):
            MessageValidator.validate_not_empty("   ", "symbol")

    def test_validate_market_format_valid(self):
        """Test market format validation with valid formats."""
        assert MessageValidator.validate_market_format("KRW-BTC") == "KRW-BTC"
        assert MessageValidator.validate_market_format("BTC-ETH") == "BTC-ETH"

    def test_validate_market_format_invalid(self):
        """Test market format validation fails for invalid formats."""
        with pytest.raises(InvalidValueError):
            MessageValidator.validate_market_format("KRWBTC")
        with pytest.raises(InvalidValueError):
            MessageValidator.validate_market_format("")


# =============================================================================
# TickerMessage Tests
# =============================================================================


class TestTickerMessage:
    """Tests for TickerMessage class."""

    def test_from_websocket_minimal(self, minimal_ticker_data):
        """Test creation from minimal WebSocket data."""
        ticker = TickerMessage.from_websocket(minimal_ticker_data)

        assert ticker.market == "KRW-BTC"
        assert ticker.trade_price == 50000000.0
        assert ticker.change == ChangeType.RISE

    def test_from_websocket_full(self, full_ticker_data):
        """Test creation from complete WebSocket data."""
        ticker = TickerMessage.from_websocket(full_ticker_data)

        assert ticker.market == "KRW-BTC"
        assert ticker.trade_price == 50000000.0
        assert ticker.change == ChangeType.RISE
        assert ticker.acc_ask_volume == 400.0
        assert ticker.acc_bid_volume == 600.0
        assert ticker.market_state == "ACTIVE"

    def test_from_websocket_with_code_field(self, minimal_ticker_data):
        """Test creation when 'code' field is used instead of 'market'."""
        data = minimal_ticker_data.copy()
        del data["market"]
        data["code"] = "KRW-ETH"

        ticker = TickerMessage.from_websocket(data)
        assert ticker.market == "KRW-ETH"

    def test_from_websocket_missing_required_field(self, minimal_ticker_data):
        """Test error when required field is missing."""
        data = minimal_ticker_data.copy()
        del data["trade_price"]

        with pytest.raises(MissingFieldError) as exc_info:
            TickerMessage.from_websocket(data)
        assert "trade_price" in str(exc_info.value)

    def test_from_websocket_missing_market(self, minimal_ticker_data):
        """Test error when market field is missing."""
        data = minimal_ticker_data.copy()
        del data["market"]

        with pytest.raises(MissingFieldError) as exc_info:
            TickerMessage.from_websocket(data)
        assert "market" in str(exc_info.value)

    def test_from_websocket_invalid_type(self, minimal_ticker_data):
        """Test error when field has invalid type."""
        data = minimal_ticker_data.copy()
        data["trade_price"] = "not_a_number"

        with pytest.raises(InvalidTypeError):
            TickerMessage.from_websocket(data)

    def test_symbol_property(self, full_ticker_data):
        """Test symbol extraction from market."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        assert ticker.symbol == "BTC"

    def test_quote_currency_property(self, full_ticker_data):
        """Test quote currency extraction from market."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        assert ticker.quote_currency == "KRW"

    def test_trade_datetime_property(self, full_ticker_data):
        """Test trade datetime conversion."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        dt = ticker.trade_datetime

        assert isinstance(dt, datetime)
        assert dt.tzinfo == timezone.utc

    def test_is_rising_property(self, full_ticker_data):
        """Test is_rising property."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        assert ticker.is_rising is True
        assert ticker.is_falling is False

    def test_volume_imbalance_property(self, full_ticker_data):
        """Test volume imbalance calculation."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        imbalance = ticker.volume_imbalance

        assert imbalance is not None
        # (600 - 400) / (600 + 400) = 0.2
        assert abs(imbalance - 0.2) < 0.001

    def test_to_dict(self, full_ticker_data):
        """Test dictionary conversion."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        data = ticker.to_dict()

        assert isinstance(data, dict)
        assert data["market"] == "KRW-BTC"
        assert data["change"] == "RISE"  # Enum converted to string
        assert data["ask_bid"] == "BID"

    def test_to_json(self, full_ticker_data):
        """Test JSON serialization."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        json_str = ticker.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["market"] == "KRW-BTC"

    def test_to_kafka_message(self, full_ticker_data):
        """Test Kafka message format."""
        ticker = TickerMessage.from_websocket(full_ticker_data)
        kafka_msg = ticker.to_kafka_message()

        assert isinstance(kafka_msg, dict)
        assert "_metadata" in kafka_msg
        assert "ingested_at_ns" in kafka_msg["_metadata"]
        assert isinstance(kafka_msg["_metadata"]["ingested_at_ns"], int)
        assert kafka_msg["_metadata"]["source"] == "upbit_websocket"


# =============================================================================
# TradeMessage Tests
# =============================================================================


class TestTradeMessage:
    """Tests for TradeMessage class."""

    def test_from_websocket(self, trade_data):
        """Test creation from WebSocket data."""
        trade = TradeMessage.from_websocket(trade_data)

        assert trade.market == "KRW-BTC"
        assert trade.trade_price == 50000000.0
        assert trade.trade_volume == 0.1
        assert trade.ask_bid == AskBid.BID

    def test_trade_value_property(self, trade_data):
        """Test trade value calculation."""
        trade = TradeMessage.from_websocket(trade_data)

        expected = 50000000.0 * 0.1
        assert trade.trade_value == expected

    def test_is_buy_property(self, trade_data):
        """Test is_buy property for BID."""
        trade = TradeMessage.from_websocket(trade_data)
        assert trade.is_buy is True
        assert trade.is_sell is False

    def test_is_sell_property(self, trade_data):
        """Test is_sell property for ASK."""
        data = trade_data.copy()
        data["ask_bid"] = "ASK"
        trade = TradeMessage.from_websocket(data)

        assert trade.is_sell is True
        assert trade.is_buy is False


# =============================================================================
# OrderbookMessage Tests
# =============================================================================


class TestOrderbookMessage:
    """Tests for OrderbookMessage class."""

    def test_from_websocket(self, orderbook_data):
        """Test creation from WebSocket data."""
        orderbook = OrderbookMessage.from_websocket(orderbook_data)

        assert orderbook.market == "KRW-BTC"
        assert orderbook.total_ask_size == 100.0
        assert orderbook.total_bid_size == 150.0
        assert len(orderbook.orderbook_units) == 2

    def test_best_prices(self, orderbook_data):
        """Test best ask/bid price properties."""
        orderbook = OrderbookMessage.from_websocket(orderbook_data)

        assert orderbook.best_ask_price == 50010000.0
        assert orderbook.best_bid_price == 50000000.0

    def test_spread_calculation(self, orderbook_data):
        """Test spread calculation."""
        orderbook = OrderbookMessage.from_websocket(orderbook_data)

        assert orderbook.spread == 10000.0  # 50010000 - 50000000
        assert orderbook.mid_price == 50005000.0

    def test_spread_bps(self, orderbook_data):
        """Test spread in basis points."""
        orderbook = OrderbookMessage.from_websocket(orderbook_data)

        # spread / mid_price * 10000
        expected_bps = (10000.0 / 50005000.0) * 10000
        assert abs(orderbook.spread_bps - expected_bps) < 0.01

    def test_imbalance_calculation(self, orderbook_data):
        """Test order book imbalance calculation."""
        orderbook = OrderbookMessage.from_websocket(orderbook_data)

        # (150 - 100) / (150 + 100) = 0.2
        assert abs(orderbook.imbalance - 0.2) < 0.001

    def test_depth_property(self, orderbook_data):
        """Test depth property."""
        orderbook = OrderbookMessage.from_websocket(orderbook_data)
        assert orderbook.depth == 2

    def test_empty_orderbook_units(self):
        """Test handling of empty orderbook units."""
        data = {
            "market": "KRW-BTC",
            "timestamp": 1707984000123,
            "total_ask_size": 0.0,
            "total_bid_size": 0.0,
            "orderbook_units": [],
        }
        orderbook = OrderbookMessage.from_websocket(data)

        assert orderbook.best_ask_price == 0.0
        assert orderbook.best_bid_price == 0.0
        assert orderbook.spread == 0.0

    def test_to_kafka_message_includes_computed_fields(self, orderbook_data):
        """Test Kafka message includes computed analytics fields."""
        orderbook = OrderbookMessage.from_websocket(orderbook_data)
        kafka_msg = orderbook.to_kafka_message()

        assert "spread" in kafka_msg
        assert "spread_bps" in kafka_msg
        assert "imbalance" in kafka_msg
        assert "best_ask_price" in kafka_msg
        assert "best_bid_price" in kafka_msg


# =============================================================================
# OrderbookUnit Tests
# =============================================================================


class TestOrderbookUnit:
    """Tests for OrderbookUnit class."""

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "ask_price": 50010000.0,
            "bid_price": 50000000.0,
            "ask_size": 1.5,
            "bid_size": 2.0,
        }
        unit = OrderbookUnit.from_dict(data)

        assert unit.ask_price == 50010000.0
        assert unit.bid_price == 50000000.0
        assert unit.ask_size == 1.5
        assert unit.bid_size == 2.0

    def test_spread_property(self):
        """Test spread calculation."""
        unit = OrderbookUnit(
            ask_price=50010000.0,
            bid_price=50000000.0,
            ask_size=1.0,
            bid_size=1.0,
        )
        assert unit.spread == 10000.0

    def test_mid_price_property(self):
        """Test mid price calculation."""
        unit = OrderbookUnit(
            ask_price=50010000.0,
            bid_price=50000000.0,
            ask_size=1.0,
            bid_size=1.0,
        )
        assert unit.mid_price == 50005000.0

    def test_immutability(self):
        """Test that OrderbookUnit is immutable (frozen)."""
        unit = OrderbookUnit(
            ask_price=50010000.0,
            bid_price=50000000.0,
            ask_size=1.0,
            bid_size=1.0,
        )
        with pytest.raises(AttributeError):
            unit.ask_price = 50020000.0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_large_numbers(self, minimal_ticker_data):
        """Test handling of very large numbers."""
        data = minimal_ticker_data.copy()
        data["trade_price"] = 999999999999999.0
        data["acc_trade_price"] = 999999999999999999.0

        ticker = TickerMessage.from_websocket(data)
        assert ticker.trade_price == 999999999999999.0

    def test_zero_values(self, minimal_ticker_data):
        """Test handling of zero values."""
        data = minimal_ticker_data.copy()
        data["trade_volume"] = 0.0
        data["change_price"] = 0.0

        ticker = TickerMessage.from_websocket(data)
        assert ticker.trade_volume == 0.0
        assert ticker.change_price == 0.0

    def test_unicode_in_market(self):
        """Test that market codes don't have unicode issues."""
        data = {
            "market": "KRW-BTC",  # ASCII only expected
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

        json_str = ticker.to_json()
        assert "KRW-BTC" in json_str
