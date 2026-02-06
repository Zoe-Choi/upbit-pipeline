"""
Kafka message handler for Upbit WebSocket data.
Routes parsed messages to appropriate Kafka topics.

Performance optimizations:
- Removed ThreadPoolExecutor overhead (Kafka producer is already async internally)
- Direct synchronous calls to producer (librdkafka handles batching)
- Optional batch mode for high-throughput scenarios
"""
from typing import Optional, List, Tuple

from src.consumers import MessageHandler
from src.models import TickerMessage, TradeMessage, OrderbookMessage
from src.producers import UpbitKafkaProducer
from src.utils import get_logger

logger = get_logger(__name__)


class KafkaMessageHandler(MessageHandler):
    """
    Message handler that forwards data to Kafka.
    
    Performance notes:
    - librdkafka (used by confluent-kafka) is internally asynchronous
    - Producer.produce() is non-blocking and adds to internal buffer
    - ThreadPoolExecutor was adding unnecessary context switch overhead
    - producer.poll(0) triggers delivery callbacks without blocking
    """
    
    def __init__(
        self,
        producer: Optional[UpbitKafkaProducer] = None,
        batch_size: int = 0,
    ):
        """
        Initialize handler.
        
        Args:
            producer: Optional Kafka producer instance
            batch_size: If > 0, enables batch mode (flush after N messages)
        """
        self._producer = producer or UpbitKafkaProducer()
        self._batch_size = batch_size
        self._pending_count = 0
        
        # Counters for monitoring
        self._ticker_count = 0
        self._trade_count = 0
        self._orderbook_count = 0
    
    def _maybe_poll(self) -> None:
        """
        Trigger poll if batch threshold reached.
        
        poll(0) is non-blocking and handles:
        - Delivery callbacks
        - Internal buffer management
        """
        self._pending_count += 1
        if self._batch_size > 0 and self._pending_count >= self._batch_size:
            self._producer._producer.poll(0)
            self._pending_count = 0
    
    async def handle_ticker(self, message: TickerMessage) -> None:
        """
        Handle ticker message by forwarding to Kafka.
        
        Performance: Direct synchronous call - produce() is non-blocking.
        
        Args:
            message: Parsed ticker message
        """
        try:
            kafka_message = message.to_kafka_message()
            self._producer.produce_ticker(kafka_message)
            self._maybe_poll()
        except Exception as e:
            logger.error("Failed to produce ticker: %s", e)
        
        self._ticker_count += 1
        if self._ticker_count % 1000 == 0:
            logger.debug("Produced %d ticker messages", self._ticker_count)
    
    async def handle_trade(self, message: TradeMessage) -> None:
        """
        Handle trade message by forwarding to Kafka.
        
        Args:
            message: Parsed trade message
        """
        try:
            kafka_message = message.to_kafka_message()
            self._producer.produce_trade(kafka_message)
            self._maybe_poll()
        except Exception as e:
            logger.error("Failed to produce trade: %s", e)
        
        self._trade_count += 1
        if self._trade_count % 1000 == 0:
            logger.debug("Produced %d trade messages", self._trade_count)
    
    async def handle_orderbook(self, message: OrderbookMessage) -> None:
        """
        Handle orderbook message by forwarding to Kafka.
        
        Args:
            message: Parsed orderbook message
        """
        try:
            kafka_message = message.to_kafka_message()
            self._producer.produce_orderbook(kafka_message)
            self._maybe_poll()
        except Exception as e:
            logger.error("Failed to produce orderbook: %s", e)
        
        self._orderbook_count += 1
        if self._orderbook_count % 1000 == 0:
            logger.debug("Produced %d orderbook messages", self._orderbook_count)
    
    def flush(self) -> None:
        """Flush pending Kafka messages."""
        self._producer.flush()
    
    def close(self) -> None:
        """Clean up resources."""
        logger.info(
            "Handler stats - Ticker: %d, Trade: %d, Orderbook: %d",
            self._ticker_count, self._trade_count, self._orderbook_count
        )
        self.flush()
    
    @property
    def stats(self) -> dict:
        """Get handler statistics."""
        return {
            "ticker_count": self._ticker_count,
            "trade_count": self._trade_count,
            "orderbook_count": self._orderbook_count,
            "producer_stats": self._producer.stats,
        }
