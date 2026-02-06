"""
Data models for Upbit market data.

This module provides strongly-typed dataclasses for parsing
and serializing WebSocket messages from Upbit.
"""
from .base import BaseMessage, MessageValidator
from .enums import (
    AskBid,
    ChangeType,
    MarketState,
    MarketWarning,
    StreamType,
    SubscriptionType,
)
from .orderbook import OrderbookMessage, OrderbookUnit
from .ticker import TickerMessage
from .trade import TradeMessage

__all__ = [
    # Base classes
    "BaseMessage",
    "MessageValidator",
    # Enums
    "AskBid",
    "ChangeType",
    "MarketState",
    "MarketWarning",
    "StreamType",
    "SubscriptionType",
    # Messages
    "OrderbookMessage",
    "OrderbookUnit",
    "TickerMessage",
    "TradeMessage",
]
