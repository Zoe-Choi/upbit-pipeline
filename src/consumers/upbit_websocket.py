"""
Upbit WebSocket client for real-time market data.
Implements automatic reconnection, heartbeat, and message routing.
"""
import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Callable, Dict, Any, Set
import signal

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

from src.config import UpbitConfig, get_config
from src.models import TickerMessage, TradeMessage, OrderbookMessage
from src.models.enums import SubscriptionType
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class Subscription:
    """WebSocket subscription configuration."""
    type: SubscriptionType
    codes: List[str]
    is_only_realtime: bool = True
    is_only_snapshot: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to WebSocket request format."""
        result = {
            "type": self.type.value,
            "codes": self.codes,
        }
        if self.is_only_realtime:
            result["is_only_realtime"] = True
        if self.is_only_snapshot:
            result["is_only_snapshot"] = True
        return result


class MessageHandler(ABC):
    """Abstract base class for message handlers."""
    
    @abstractmethod
    async def handle_ticker(self, message: TickerMessage) -> None:
        """Handle ticker message."""
        pass
    
    @abstractmethod
    async def handle_trade(self, message: TradeMessage) -> None:
        """Handle trade message."""
        pass
    
    @abstractmethod
    async def handle_orderbook(self, message: OrderbookMessage) -> None:
        """Handle orderbook message."""
        pass


class UpbitWebSocketClient:
    """
    Upbit WebSocket client with automatic reconnection.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Heartbeat (PING/PONG) support
    - Multiple subscription types
    - Graceful shutdown
    """
    
    def __init__(
        self,
        handler: MessageHandler,
        config: Optional[UpbitConfig] = None,
        subscriptions: Optional[List[Subscription]] = None,
    ):
        """
        Initialize WebSocket client.
        
        Args:
            handler: Message handler implementation
            config: Optional Upbit configuration
            subscriptions: Optional list of subscriptions
        """
        self._config = config or get_config().upbit
        self._handler = handler
        self._subscriptions = subscriptions or []
        
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_count = 0
        self._message_count = 0
        self._connected_markets: Set[str] = set()
        
        # Event for graceful shutdown
        self._shutdown_event = asyncio.Event()
    
    def add_subscription(self, subscription: Subscription) -> None:
        """Add a subscription."""
        self._subscriptions.append(subscription)
        for code in subscription.codes:
            self._connected_markets.add(code)
    
    def subscribe_ticker(self, codes: List[str], realtime_only: bool = True) -> None:
        """Subscribe to ticker updates."""
        self.add_subscription(Subscription(
            type=SubscriptionType.TICKER,
            codes=codes,
            is_only_realtime=realtime_only,
        ))
    
    def subscribe_trade(self, codes: List[str], realtime_only: bool = True) -> None:
        """Subscribe to trade updates."""
        self.add_subscription(Subscription(
            type=SubscriptionType.TRADE,
            codes=codes,
            is_only_realtime=realtime_only,
        ))
    
    def subscribe_orderbook(self, codes: List[str], realtime_only: bool = True) -> None:
        """Subscribe to orderbook updates."""
        self.add_subscription(Subscription(
            type=SubscriptionType.ORDERBOOK,
            codes=codes,
            is_only_realtime=realtime_only,
        ))
    
    def _build_subscribe_message(self) -> str:
        """Build subscription request message."""
        ticket = {"ticket": str(uuid.uuid4())}
        subscriptions = [sub.to_dict() for sub in self._subscriptions]
        format_obj = {"format": "DEFAULT"}
        
        message = [ticket] + subscriptions + [format_obj]
        return json.dumps(message)
    
    async def _connect(self) -> None:
        """Establish WebSocket connection."""
        logger.info("Connecting to Upbit WebSocket: %s", self._config.websocket_url)
        
        self._websocket = await websockets.connect(
            self._config.websocket_url,
            ping_interval=self._config.ping_interval,
            ping_timeout=self._config.ping_timeout,
            close_timeout=10,
        )
        
        # Send subscription request
        subscribe_msg = self._build_subscribe_message()
        await self._websocket.send(subscribe_msg)
        logger.info("Subscribed to %d markets", len(self._connected_markets))
        
        self._reconnect_count = 0
    
    async def _handle_message(self, raw_message: bytes | str) -> None:
        """
        Parse and route incoming message.
        
        Args:
            raw_message: Raw WebSocket message
        """
        try:
            # Parse message
            if isinstance(raw_message, bytes):
                data = json.loads(raw_message.decode("utf-8"))
            else:
                data = json.loads(raw_message)
            
            # Handle status messages
            if "status" in data:
                logger.debug("Status message: %s", data.get("status"))
                return
            
            # Handle error messages
            if "error" in data:
                logger.error("WebSocket error: %s", data["error"])
                return
            
            # Route based on message type
            msg_type = data.get("type", "").lower()
            
            # 타입이 없으면 스킵 (status 메시지 등)
            if not msg_type:
                return
            
            if msg_type == "ticker":
                ticker = TickerMessage.from_websocket(data)
                await self._handler.handle_ticker(ticker)
            elif msg_type == "trade":
                trade = TradeMessage.from_websocket(data)
                await self._handler.handle_trade(trade)
            elif msg_type == "orderbook":
                orderbook = OrderbookMessage.from_websocket(data)
                await self._handler.handle_orderbook(orderbook)
            else:
                logger.debug("Skipping message type: %s", msg_type)
            
            self._message_count += 1
            if self._message_count % 10000 == 0:
                logger.info("Processed %d messages", self._message_count)
                
        except json.JSONDecodeError as e:
            logger.error("Failed to parse message: %s", e)
        except KeyError as e:
            logger.debug("Missing required field in message: %s, data: %s", e, data)
        except Exception as e:
            logger.error("Error handling message: %s", e, exc_info=True)
    
    async def _listen(self) -> None:
        """Listen for incoming messages."""
        try:
            async for message in self._websocket:
                if self._shutdown_event.is_set():
                    break
                await self._handle_message(message)
        except ConnectionClosedOK:
            logger.info("WebSocket connection closed normally")
        except ConnectionClosedError as e:
            logger.warning("WebSocket connection closed with error: %s", e)
            raise
        except ConnectionClosed as e:
            logger.warning("WebSocket connection closed: %s", e)
            raise
    
    async def _reconnect_with_backoff(self) -> bool:
        """
        Attempt reconnection with exponential backoff.
        
        Returns:
            True if reconnection successful, False if max attempts reached
        """
        if self._reconnect_count >= self._config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False
        
        self._reconnect_count += 1
        delay = min(
            self._config.reconnect_delay * (2 ** (self._reconnect_count - 1)),
            60  # Max 60 seconds
        )
        
        logger.info(
            "Reconnecting in %d seconds (attempt %d/%d)",
            delay, self._reconnect_count, self._config.max_reconnect_attempts
        )
        
        await asyncio.sleep(delay)
        
        try:
            await self._connect()
            return True
        except Exception as e:
            logger.error("Reconnection failed: %s", e)
            return await self._reconnect_with_backoff()
    
    async def run(self) -> None:
        """Run the WebSocket client."""
        self._running = True
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        
        logger.info("Starting Upbit WebSocket client")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                await self._connect()
                await self._listen()
            except Exception as e:
                logger.error("Connection error: %s", e)
                
                if self._shutdown_event.is_set():
                    break
                    
                if not await self._reconnect_with_backoff():
                    break
        
        logger.info(
            "WebSocket client stopped. Total messages processed: %d",
            self._message_count
        )
    
    async def stop(self) -> None:
        """Gracefully stop the client."""
        logger.info("Stopping WebSocket client...")
        self._running = False
        self._shutdown_event.set()
        
        if self._websocket:
            await self._websocket.close()
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._websocket is not None and self._websocket.open
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "message_count": self._message_count,
            "reconnect_count": self._reconnect_count,
            "connected_markets": len(self._connected_markets),
            "is_connected": self.is_connected,
        }
