"""
Enumerations for Upbit market data.

Centralizes all enum definitions to ensure consistency
across the codebase and prevent magic strings.
"""
from enum import Enum, unique


@unique
class ChangeType(str, Enum):
    """Price change direction."""

    RISE = "RISE"
    EVEN = "EVEN"
    FALL = "FALL"

    @classmethod
    def from_value(cls, value: str) -> "ChangeType":
        """
        Create from string value with fallback to EVEN.
        
        Args:
            value: String value to convert
            
        Returns:
            ChangeType enum member
        """
        try:
            return cls(value.upper())
        except (ValueError, AttributeError):
            return cls.EVEN


@unique
class AskBid(str, Enum):
    """Trade direction (ask/bid)."""

    ASK = "ASK"
    BID = "BID"

    @classmethod
    def from_value(cls, value: str) -> "AskBid":
        """
        Create from string value.
        
        Args:
            value: String value to convert
            
        Returns:
            AskBid enum member
            
        Raises:
            ValueError: If value is not valid
        """
        return cls(value.upper())

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy order (BID)."""
        return self == AskBid.BID

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell order (ASK)."""
        return self == AskBid.ASK


@unique
class StreamType(str, Enum):
    """WebSocket stream type."""

    SNAPSHOT = "SNAPSHOT"
    REALTIME = "REALTIME"

    @classmethod
    def from_value(cls, value: str) -> "StreamType":
        """
        Create from string value with fallback to REALTIME.
        
        Args:
            value: String value to convert
            
        Returns:
            StreamType enum member
        """
        try:
            return cls(value.upper())
        except (ValueError, AttributeError):
            return cls.REALTIME


@unique
class MarketState(str, Enum):
    """Market trading state."""

    PREVIEW = "PREVIEW"
    ACTIVE = "ACTIVE"
    DELISTED = "DELISTED"

    @classmethod
    def from_value(cls, value: str) -> "MarketState":
        """Create from string value with fallback to ACTIVE."""
        try:
            return cls(value.upper())
        except (ValueError, AttributeError):
            return cls.ACTIVE


@unique
class MarketWarning(str, Enum):
    """Market warning status."""

    NONE = "NONE"
    CAUTION = "CAUTION"

    @classmethod
    def from_value(cls, value: str) -> "MarketWarning":
        """Create from string value with fallback to NONE."""
        try:
            return cls(value.upper())
        except (ValueError, AttributeError):
            return cls.NONE


@unique
class SubscriptionType(str, Enum):
    """WebSocket subscription types."""

    TICKER = "ticker"
    TRADE = "trade"
    ORDERBOOK = "orderbook"

    def __str__(self) -> str:
        return self.value
