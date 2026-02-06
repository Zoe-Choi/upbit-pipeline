"""
Orderbook data models for Upbit market data.

Based on Upbit WebSocket API specification:
https://docs.upbit.com/kr/reference/websocket-guide
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from .base import BaseMessage, MessageValidator
from .enums import StreamType


@dataclass(frozen=True)
class OrderbookUnit:
    """
    Single orderbook price level.
    
    Represents one level of the order book with
    ask (sell) and bid (buy) information.
    
    Attributes:
        ask_price: Ask (sell) price at this level
        bid_price: Bid (buy) price at this level
        ask_size: Total ask volume at this price
        bid_size: Total bid volume at this price
    """

    ask_price: float
    bid_price: float
    ask_size: float
    bid_size: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderbookUnit":
        """
        Create from dictionary.
        
        Args:
            data: Dictionary with orderbook unit data
            
        Returns:
            OrderbookUnit instance
        """
        return cls(
            ask_price=float(data.get("ask_price", 0)),
            bid_price=float(data.get("bid_price", 0)),
            ask_size=float(data.get("ask_size", 0)),
            bid_size=float(data.get("bid_size", 0)),
        )

    @property
    def spread(self) -> float:
        """Calculate spread between ask and bid."""
        return self.ask_price - self.bid_price

    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        return (self.ask_price + self.bid_price) / 2

    @property
    def spread_bps(self) -> float:
        """Calculate spread in basis points."""
        if self.mid_price == 0:
            return 0.0
        return (self.spread / self.mid_price) * 10000


@dataclass(frozen=False)
class OrderbookMessage(BaseMessage):
    """
    Upbit Orderbook WebSocket message.
    
    Contains order book depth information for a trading pair.
    
    Attributes:
        market: Trading pair code (e.g., 'KRW-BTC')
        timestamp: Message timestamp
        total_ask_size: Total ask volume across all levels
        total_bid_size: Total bid volume across all levels
        orderbook_units: List of orderbook levels
        stream_type: Stream type (SNAPSHOT/REALTIME)
        level: Orderbook depth level
    """

    REQUIRED_FIELDS = (
        "timestamp",
        "total_ask_size",
        "total_bid_size",
    )

    # Market identification
    market: str

    # Timestamp
    timestamp: int

    # Aggregated sizes
    total_ask_size: float
    total_bid_size: float

    # Orderbook levels
    orderbook_units: List[OrderbookUnit] = field(default_factory=list)

    # Metadata
    stream_type: StreamType = StreamType.REALTIME
    level: int = 0

    @classmethod
    def from_websocket(cls, data: Dict[str, Any]) -> "OrderbookMessage":
        """
        Create OrderbookMessage from WebSocket response.

        Args:
            data: Raw WebSocket message dictionary

        Returns:
            OrderbookMessage instance

        Raises:
            MissingFieldError: If required field is missing
            InvalidTypeError: If field has wrong type
        """
        cls._validate_required_fields(data)
        market = cls._extract_market(data)
        MessageValidator.validate_market_format(market)

        units = [
            OrderbookUnit.from_dict(unit)
            for unit in data.get("orderbook_units", [])
        ]

        return cls(
            market=market,
            timestamp=cls._safe_int(data["timestamp"], "timestamp"),
            total_ask_size=cls._safe_float(
                data["total_ask_size"], "total_ask_size"
            ),
            total_bid_size=cls._safe_float(
                data["total_bid_size"], "total_bid_size"
            ),
            orderbook_units=units,
            stream_type=StreamType.from_value(data.get("stream_type", "REALTIME")),
            level=cls._safe_int(data.get("level", 0), "level"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "market": self.market,
            "timestamp": self.timestamp,
            "total_ask_size": self.total_ask_size,
            "total_bid_size": self.total_bid_size,
            "orderbook_units": [asdict(unit) for unit in self.orderbook_units],
            "stream_type": self.stream_type.value,
            "level": self.level,
        }

    def to_kafka_message(self) -> Dict[str, Any]:
        """
        Convert to Kafka message format with additional computed fields.
        
        Adds spread and imbalance metrics for downstream analytics.
        
        Performance: Calculates derived values once and reuses them.
        """
        data = super().to_kafka_message()
        
        # Pre-compute values to avoid repeated property access
        best_ask = self.best_ask_price
        best_bid = self.best_bid_price
        spread = best_ask - best_bid
        mid = (best_ask + best_bid) / 2 if (best_ask + best_bid) > 0 else 0
        
        # Add computed fields for analytics
        data["best_ask_price"] = best_ask
        data["best_bid_price"] = best_bid
        data["spread"] = spread
        data["spread_bps"] = (spread / mid * 10000) if mid > 0 else 0.0
        data["imbalance"] = self.imbalance
        
        return data

    @property
    def message_datetime(self) -> datetime:
        """Get message datetime from timestamp."""
        return datetime.fromtimestamp(
            self.timestamp / 1000,
            tz=timezone.utc,
        )

    @property
    def best_ask_price(self) -> float:
        """Get best (lowest) ask price."""
        if not self.orderbook_units:
            return 0.0
        return self.orderbook_units[0].ask_price

    @property
    def best_bid_price(self) -> float:
        """Get best (highest) bid price."""
        if not self.orderbook_units:
            return 0.0
        return self.orderbook_units[0].bid_price

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.best_ask_price - self.best_bid_price

    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        return (self.best_ask_price + self.best_bid_price) / 2

    @property
    def spread_bps(self) -> float:
        """Calculate spread in basis points."""
        if self.mid_price == 0:
            return 0.0
        return (self.spread / self.mid_price) * 10000

    @property
    def spread_rate(self) -> float:
        """Calculate spread as percentage of mid price."""
        if self.mid_price == 0:
            return 0.0
        return (self.spread / self.mid_price) * 100

    @property
    def imbalance(self) -> float:
        """
        Calculate order book imbalance.
        
        Returns:
            Value between -1 and 1.
            Positive means more bid volume (bullish).
            Negative means more ask volume (bearish).
        """
        total = self.total_ask_size + self.total_bid_size
        if total == 0:
            return 0.0
        return (self.total_bid_size - self.total_ask_size) / total

    @property
    def depth(self) -> int:
        """Number of orderbook levels."""
        return len(self.orderbook_units)

    def get_volume_at_price(self, price: float, tolerance: float = 0.01) -> float:
        """
        Get total volume at a specific price level.
        
        Args:
            price: Target price
            tolerance: Price tolerance (percentage)
            
        Returns:
            Total volume (ask + bid) near the price
        """
        volume = 0.0
        for unit in self.orderbook_units:
            if abs(unit.ask_price - price) / price <= tolerance:
                volume += unit.ask_size
            if abs(unit.bid_price - price) / price <= tolerance:
                volume += unit.bid_size
        return volume
