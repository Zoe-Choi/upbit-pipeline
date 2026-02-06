"""
Kafka producer for Upbit market data.
Thread-safe producer with delivery callbacks and graceful shutdown.

Performance optimizations:
- Pre-encoded headers cache (avoid repeated .encode() calls)
- Singleton pattern for connection reuse
- Non-blocking produce with internal batching
"""
from typing import Dict, Any, Optional, Callable, List, Tuple
from threading import Lock
import atexit

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from src.config import KafkaConfig, get_config
from src.utils import get_logger, JSONSerializer, create_key_serializer

logger = get_logger(__name__)


class UpbitKafkaProducer:
    """
    Thread-safe Kafka producer for Upbit market data.
    
    Handles message serialization, delivery confirmation,
    and graceful shutdown.
    
    Performance notes:
    - Headers are pre-encoded at class level
    - produce() is non-blocking (adds to internal buffer)
    - librdkafka handles batching and compression internally
    """
    
    _instance: Optional["UpbitKafkaProducer"] = None
    _lock: Lock = Lock()
    
    # Pre-encoded headers cache - avoid repeated .encode() calls
    # Each header is a list of (key, value) tuples with bytes values
    _HEADERS_CACHE: Dict[str, List[Tuple[str, bytes]]] = {
        "ticker": [("type", b"ticker")],
        "trade": [("type", b"trade")],
        "orderbook": [("type", b"orderbook")],
    }
    
    def __new__(cls, config: Optional[KafkaConfig] = None) -> "UpbitKafkaProducer":
        """Singleton pattern for thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
    
    def __init__(self, config: Optional[KafkaConfig] = None):
        """
        Initialize Kafka producer.
        
        Args:
            config: Optional Kafka configuration
        """
        if self._initialized:
            return
            
        self._config = config or get_config().kafka
        self._serializer = JSONSerializer()
        self._key_serializer = create_key_serializer()
        
        self._producer = Producer({
            "bootstrap.servers": self._config.bootstrap_servers,
            "acks": self._config.acks,
            "retries": self._config.retries,
            "linger.ms": self._config.linger_ms,
            "batch.size": self._config.batch_size,
            "compression.type": self._config.compression_type,
            "client.id": "upbit-pipeline-producer",
        })
        
        self._delivery_count = 0
        self._error_count = 0
        
        # Register shutdown hook
        atexit.register(self.close)
        
        self._initialized = True
        logger.info(
            "Kafka producer initialized with bootstrap servers: %s",
            self._config.bootstrap_servers
        )
    
    def _delivery_callback(self, err, msg) -> None:
        """
        Handle delivery confirmation.
        
        Args:
            err: Error if delivery failed
            msg: Delivered message
        """
        if err is not None:
            self._error_count += 1
            logger.error(
                "Message delivery failed: %s [topic=%s, partition=%s]",
                err, msg.topic(), msg.partition()
            )
        else:
            self._delivery_count += 1
            if self._delivery_count % 1000 == 0:
                logger.debug(
                    "Delivered %d messages (errors: %d)",
                    self._delivery_count, self._error_count
                )
    
    def produce(
        self,
        topic: str,
        value: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        callback: Optional[Callable] = None,
    ) -> None:
        """
        Produce a message to Kafka.
        
        Args:
            topic: Target topic name
            value: Message value (will be JSON serialized)
            key: Optional message key (for partitioning)
            headers: Optional message headers
            callback: Optional delivery callback
        """
        try:
            serialized_value = self._serializer(value)
            serialized_key = self._key_serializer(key) if key else None
            
            kafka_headers = None
            if headers:
                kafka_headers = [
                    (k, v.encode("utf-8") if isinstance(v, str) else v)
                    for k, v in headers.items()
                ]
            
            self._producer.produce(
                topic=topic,
                value=serialized_value,
                key=serialized_key,
                headers=kafka_headers,
                callback=callback or self._delivery_callback,
            )
            
            # Trigger delivery callbacks periodically
            self._producer.poll(0)
            
        except BufferError:
            logger.warning("Producer buffer full, waiting...")
            self._producer.poll(1)
            # Retry once
            self._producer.produce(
                topic=topic,
                value=serialized_value,
                key=serialized_key,
                headers=kafka_headers,
                callback=callback or self._delivery_callback,
            )
        except Exception as e:
            logger.error("Failed to produce message: %s", e)
            raise
    
    def _produce_with_cached_headers(
        self,
        topic: str,
        value: Dict[str, Any],
        key: str,
        headers_key: str,
    ) -> None:
        """
        Produce message with pre-cached headers.
        
        Performance: Avoids dict creation and .encode() per message.
        
        Args:
            topic: Target topic
            value: Message value
            key: Partition key
            headers_key: Key to lookup in _HEADERS_CACHE
        """
        try:
            serialized_value = self._serializer(value)
            serialized_key = self._key_serializer(key) if key else None
            
            self._producer.produce(
                topic=topic,
                value=serialized_value,
                key=serialized_key,
                headers=self._HEADERS_CACHE.get(headers_key),
                callback=self._delivery_callback,
            )
            
            # Non-blocking poll
            self._producer.poll(0)
            
        except BufferError:
            logger.warning("Producer buffer full, waiting...")
            self._producer.poll(1)
            # Retry once
            self._producer.produce(
                topic=topic,
                value=serialized_value,
                key=serialized_key,
                headers=self._HEADERS_CACHE.get(headers_key),
                callback=self._delivery_callback,
            )
        except Exception as e:
            logger.error("Failed to produce message: %s", e)
            raise
    
    def produce_ticker(self, message: Dict[str, Any]) -> None:
        """Produce ticker message to configured topic."""
        market = message.get("market", "unknown")
        self._produce_with_cached_headers(
            topic=self._config.topic_ticker,
            value=message,
            key=market,
            headers_key="ticker",
        )
    
    def produce_trade(self, message: Dict[str, Any]) -> None:
        """Produce trade message to configured topic."""
        market = message.get("market", "unknown")
        self._produce_with_cached_headers(
            topic=self._config.topic_trade,
            value=message,
            key=market,
            headers_key="trade",
        )
    
    def produce_orderbook(self, message: Dict[str, Any]) -> None:
        """Produce orderbook message to configured topic."""
        market = message.get("market", "unknown")
        self._produce_with_cached_headers(
            topic=self._config.topic_orderbook,
            value=message,
            key=market,
            headers_key="orderbook",
        )
    
    def flush(self, timeout: float = 10.0) -> int:
        """
        Flush pending messages.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            Number of messages still in queue
        """
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            logger.warning("%d messages still in queue after flush", remaining)
        return remaining
    
    def close(self) -> None:
        """Gracefully shutdown the producer."""
        logger.info("Shutting down Kafka producer...")
        remaining = self.flush(timeout=30.0)
        if remaining == 0:
            logger.info(
                "Producer shutdown complete. Delivered: %d, Errors: %d",
                self._delivery_count, self._error_count
            )
        else:
            logger.warning(
                "Producer shutdown with %d messages remaining", remaining
            )
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get producer statistics."""
        return {
            "delivered": self._delivery_count,
            "errors": self._error_count,
        }


def ensure_topics_exist(topics: list[str], num_partitions: int = 3, replication_factor: int = 3) -> None:
    """
    Ensure Kafka topics exist, create if not.
    
    Args:
        topics: List of topic names
        num_partitions: Number of partitions per topic
        replication_factor: Replication factor
    """
    config = get_config().kafka
    admin_client = AdminClient({
        "bootstrap.servers": config.bootstrap_servers,
    })
    
    # Get existing topics
    existing_topics = set(admin_client.list_topics().topics.keys())
    
    # Create missing topics
    new_topics = [
        NewTopic(topic, num_partitions=num_partitions, replication_factor=replication_factor)
        for topic in topics
        if topic not in existing_topics
    ]
    
    if new_topics:
        futures = admin_client.create_topics(new_topics)
        for topic, future in futures.items():
            try:
                future.result()
                logger.info("Created topic: %s", topic)
            except Exception as e:
                logger.error("Failed to create topic %s: %s", topic, e)
    else:
        logger.info("All topics already exist")
