"""
Trade data models for Upbit market data.

Based on Upbit WebSocket API specification:
https://docs.upbit.com/kr/reference/websocket-guide
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from .base import BaseMessage, MessageValidator
from .enums import AskBid, ChangeType, StreamType


@dataclass(frozen=False)
class TradeMessage(BaseMessage):
    """
    Upbit Trade WebSocket message.
    
    Contains real-time trade execution information.
    
    Attributes:
        market: Trading pair code (e.g., 'KRW-BTC')
        trade_price: Trade execution price
        trade_volume: Trade volume
        ask_bid: Trade direction (ASK/BID)
        trade_date: Trade date (YYYYMMDD)
        trade_time: Trade time (HHMMSS)
        trade_timestamp: Trade timestamp in milliseconds
        timestamp: Message timestamp
        prev_closing_price: Previous day's closing price
        change: Price change direction
        change_price: Absolute price change
        sequential_id: Unique trade identifier
        stream_type: Stream type (SNAPSHOT/REALTIME)
    """

    REQUIRED_FIELDS = (
        "trade_price",
        "trade_volume",
        "ask_bid",
        "trade_timestamp",
        "timestamp",
        "sequential_id",
    )

    # Market identification
    market: str

    # Trade information
    trade_price: float
    trade_volume: float
    ask_bid: AskBid

    # Time information
    trade_date: str
    trade_time: str
    trade_timestamp: int
    timestamp: int

    # Price change
    prev_closing_price: float
    change: ChangeType
    change_price: float

    # Sequence
    sequential_id: int

    # Metadata
    stream_type: StreamType = StreamType.REALTIME

    @classmethod
    def from_websocket(cls, data: Dict[str, Any]) -> "TradeMessage":
        """
        Create TradeMessage from WebSocket response.

        Args:
            data: Raw WebSocket message dictionary

        Returns:
            TradeMessage instance

        Raises:
            MissingFieldError: If required field is missing
            InvalidTypeError: If field has wrong type
        """
        cls._validate_required_fields(data)
        market = cls._extract_market(data)
        MessageValidator.validate_market_format(market)

        return cls(
            market=market,
            trade_price=cls._safe_float(data["trade_price"], "trade_price"),
            trade_volume=cls._safe_float(data["trade_volume"], "trade_volume"),
            ask_bid=AskBid.from_value(data["ask_bid"]),
            trade_date=data.get("trade_date", ""),
            trade_time=data.get("trade_time", ""),
            trade_timestamp=cls._safe_int(data["trade_timestamp"], "trade_timestamp"),
            timestamp=cls._safe_int(data["timestamp"], "timestamp"),
            prev_closing_price=cls._safe_float(
                data.get("prev_closing_price", 0), "prev_closing_price"
            ),
            change=ChangeType.from_value(data.get("change", "EVEN")),
            change_price=cls._safe_float(data.get("change_price", 0), "change_price"),
            sequential_id=cls._safe_int(data["sequential_id"], "sequential_id"),
            stream_type=StreamType.from_value(data.get("stream_type", "REALTIME")),
        )

    def _convert_enums(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert enum values to their string representation."""
        data["ask_bid"] = self.ask_bid.value
        data["change"] = self.change.value
        data["stream_type"] = self.stream_type.value
        return data

    @property
    def trade_datetime(self) -> datetime:
        """Get trade datetime from timestamp."""
        return datetime.fromtimestamp(
            self.trade_timestamp / 1000,
            tz=timezone.utc,
        )

    @property
    def trade_value(self) -> float:
        """Calculate trade value (price * volume)."""
        return self.trade_price * self.trade_volume

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy trade."""
        return self.ask_bid.is_buy

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell trade."""
        return self.ask_bid.is_sell

    @property
    def trade_value_krw(self) -> float:
        """
        Get trade value in KRW.
        
        Same as trade_value for KRW pairs.
        """
        return self.trade_value
