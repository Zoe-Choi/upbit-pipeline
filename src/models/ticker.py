"""
Ticker data models for Upbit market data.

Based on Upbit WebSocket API specification:
https://docs.upbit.com/kr/reference/websocket-guide
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .base import BaseMessage, MessageValidator
from .enums import ChangeType, AskBid, StreamType


@dataclass(frozen=False)
class TickerMessage(BaseMessage):
    """
    Upbit Ticker WebSocket message.
    
    Contains real-time price, volume, and change information
    for a trading pair.
    
    Attributes:
        market: Trading pair code (e.g., 'KRW-BTC')
        trade_price: Current trade price
        opening_price: Opening price for the day
        high_price: Highest price for the day
        low_price: Lowest price for the day
        prev_closing_price: Previous day's closing price
        change: Price change direction (RISE/EVEN/FALL)
        change_price: Absolute price change
        change_rate: Price change rate (0.01 = 1%)
        signed_change_price: Signed price change
        signed_change_rate: Signed price change rate
        trade_volume: Last trade volume
        acc_trade_volume: Accumulated trade volume
        acc_trade_volume_24h: 24-hour accumulated trade volume
        acc_trade_price: Accumulated trade price
        acc_trade_price_24h: 24-hour accumulated trade price
        trade_date: Trade date (YYYYMMDD)
        trade_time: Trade time (HHMMSS)
        trade_timestamp: Trade timestamp in milliseconds
        ask_bid: Trade direction (ASK/BID)
        highest_52_week_price: 52-week high price
        highest_52_week_date: Date of 52-week high
        lowest_52_week_price: 52-week low price
        lowest_52_week_date: Date of 52-week low
        timestamp: Message timestamp
        stream_type: Stream type (SNAPSHOT/REALTIME)
        acc_ask_volume: Accumulated ask volume (optional)
        acc_bid_volume: Accumulated bid volume (optional)
        market_state: Market state (optional)
        market_warning: Market warning (optional)
    """

    REQUIRED_FIELDS = (
        "trade_price",
        "opening_price",
        "high_price",
        "low_price",
        "prev_closing_price",
        "change",
        "trade_timestamp",
        "timestamp",
    )

    # Market identification
    market: str

    # Price information
    trade_price: float
    opening_price: float
    high_price: float
    low_price: float
    prev_closing_price: float

    # Change information
    change: ChangeType
    change_price: float
    change_rate: float
    signed_change_price: float
    signed_change_rate: float

    # Volume information
    trade_volume: float
    acc_trade_volume: float
    acc_trade_volume_24h: float
    acc_trade_price: float
    acc_trade_price_24h: float

    # Trade information
    trade_date: str
    trade_time: str
    trade_timestamp: int
    ask_bid: AskBid

    # 52-week information
    highest_52_week_price: float
    highest_52_week_date: str
    lowest_52_week_price: float
    lowest_52_week_date: str

    # Metadata
    timestamp: int
    stream_type: StreamType = StreamType.REALTIME

    # Optional fields
    acc_ask_volume: Optional[float] = None
    acc_bid_volume: Optional[float] = None
    market_state: Optional[str] = None
    market_warning: Optional[str] = None

    @classmethod
    def from_websocket(cls, data: Dict[str, Any]) -> "TickerMessage":
        """
        Create TickerMessage from WebSocket response.

        Args:
            data: Raw WebSocket message dictionary

        Returns:
            TickerMessage instance

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
            opening_price=cls._safe_float(data["opening_price"], "opening_price"),
            high_price=cls._safe_float(data["high_price"], "high_price"),
            low_price=cls._safe_float(data["low_price"], "low_price"),
            prev_closing_price=cls._safe_float(
                data["prev_closing_price"], "prev_closing_price"
            ),
            change=ChangeType.from_value(data["change"]),
            change_price=cls._safe_float(data.get("change_price", 0), "change_price"),
            change_rate=cls._safe_float(data.get("change_rate", 0), "change_rate"),
            signed_change_price=cls._safe_float(
                data.get("signed_change_price", 0), "signed_change_price"
            ),
            signed_change_rate=cls._safe_float(
                data.get("signed_change_rate", 0), "signed_change_rate"
            ),
            trade_volume=cls._safe_float(data.get("trade_volume", 0), "trade_volume"),
            acc_trade_volume=cls._safe_float(
                data.get("acc_trade_volume", 0), "acc_trade_volume"
            ),
            acc_trade_volume_24h=cls._safe_float(
                data.get("acc_trade_volume_24h", 0), "acc_trade_volume_24h"
            ),
            acc_trade_price=cls._safe_float(
                data.get("acc_trade_price", 0), "acc_trade_price"
            ),
            acc_trade_price_24h=cls._safe_float(
                data.get("acc_trade_price_24h", 0), "acc_trade_price_24h"
            ),
            trade_date=data.get("trade_date", ""),
            trade_time=data.get("trade_time", ""),
            trade_timestamp=cls._safe_int(data["trade_timestamp"], "trade_timestamp"),
            ask_bid=AskBid.from_value(data.get("ask_bid", "BID")),
            highest_52_week_price=cls._safe_float(
                data.get("highest_52_week_price", 0), "highest_52_week_price"
            ),
            highest_52_week_date=data.get("highest_52_week_date", ""),
            lowest_52_week_price=cls._safe_float(
                data.get("lowest_52_week_price", 0), "lowest_52_week_price"
            ),
            lowest_52_week_date=data.get("lowest_52_week_date", ""),
            timestamp=cls._safe_int(data["timestamp"], "timestamp"),
            stream_type=StreamType.from_value(data.get("stream_type", "REALTIME")),
            acc_ask_volume=(
                cls._safe_float(data["acc_ask_volume"], "acc_ask_volume")
                if data.get("acc_ask_volume") is not None
                else None
            ),
            acc_bid_volume=(
                cls._safe_float(data["acc_bid_volume"], "acc_bid_volume")
                if data.get("acc_bid_volume") is not None
                else None
            ),
            market_state=data.get("market_state"),
            market_warning=data.get("market_warning"),
        )

    def _convert_enums(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert enum values to their string representation."""
        data["change"] = self.change.value
        data["ask_bid"] = self.ask_bid.value
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
    def is_rising(self) -> bool:
        """Check if price is rising."""
        return self.change == ChangeType.RISE

    @property
    def is_falling(self) -> bool:
        """Check if price is falling."""
        return self.change == ChangeType.FALL

    @property
    def price_change_percent(self) -> float:
        """Get price change as percentage."""
        return self.signed_change_rate * 100

    @property
    def volume_imbalance(self) -> Optional[float]:
        """
        Calculate volume imbalance between asks and bids.
        
        Returns:
            Imbalance ratio (-1 to 1), positive means more bids.
            None if volume data is not available.
        """
        if self.acc_ask_volume is None or self.acc_bid_volume is None:
            return None
        total = self.acc_ask_volume + self.acc_bid_volume
        if total == 0:
            return 0.0
        return (self.acc_bid_volume - self.acc_ask_volume) / total
