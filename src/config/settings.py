"""
Application configuration management.
Loads settings from environment variables with sensible defaults.
"""
from dataclasses import dataclass, field
from functools import lru_cache
from os import getenv
from typing import List


@dataclass(frozen=True)
class UpbitConfig:
    """Upbit WebSocket configuration."""
    websocket_url: str = "wss://api.upbit.com/websocket/v1"
    ping_interval: int = 30  # seconds
    ping_timeout: int = 10  # seconds
    reconnect_delay: int = 5  # seconds
    max_reconnect_attempts: int = 10


@dataclass(frozen=True)
class KafkaConfig:
    """Kafka producer configuration."""
    bootstrap_servers: str = field(
        default_factory=lambda: getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:29092,localhost:29093,localhost:29094"
        )
    )
    topic_ticker: str = field(
        default_factory=lambda: getenv("KAFKA_TOPIC_TICKER", "upbit-ticker")
    )
    topic_trade: str = field(
        default_factory=lambda: getenv("KAFKA_TOPIC_TRADE", "upbit-trade")
    )
    topic_orderbook: str = field(
        default_factory=lambda: getenv("KAFKA_TOPIC_ORDERBOOK", "upbit-orderbook")
    )
    acks: str = "all"
    retries: int = 3
    linger_ms: int = 10
    batch_size: int = 16384
    compression_type: str = "snappy"

    @property
    def bootstrap_servers_list(self) -> List[str]:
        """Return bootstrap servers as list."""
        return [s.strip() for s in self.bootstrap_servers.split(",")]


@dataclass(frozen=True)
class MinioConfig:
    """MinIO S3 configuration."""
    endpoint: str = field(
        default_factory=lambda: getenv("MINIO_ENDPOINT", "http://localhost:9000")
    )
    access_key: str = field(
        default_factory=lambda: getenv("MINIO_ROOT_USER", "minioadmin")
    )
    secret_key: str = field(
        default_factory=lambda: getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    )
    bucket_paimon: str = field(
        default_factory=lambda: getenv("MINIO_BUCKET_PAIMON", "paimon")
    )
    bucket_warehouse: str = field(
        default_factory=lambda: getenv("MINIO_BUCKET_WAREHOUSE", "warehouse")
    )


@dataclass(frozen=True)
class MarketConfig:
    """Trading pairs configuration."""
    default_markets: List[str] = field(
        default_factory=lambda: [
            "KRW-BTC", "KRW-ETH", "KRW-SOL"
        ]
    )
    
    @classmethod
    def from_env(cls) -> "MarketConfig":
        """Load markets from environment variable."""
        markets_env = getenv("UPBIT_MARKETS")
        if markets_env:
            markets = [m.strip() for m in markets_env.split(",")]
            return cls(default_markets=markets)
        return cls()


@dataclass(frozen=True)
class AppConfig:
    """Application configuration container."""
    upbit: UpbitConfig = field(default_factory=UpbitConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    minio: MinioConfig = field(default_factory=MinioConfig)
    markets: MarketConfig = field(default_factory=MarketConfig.from_env)
    log_level: str = field(
        default_factory=lambda: getenv("LOG_LEVEL", "INFO")
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Get singleton application configuration."""
    return AppConfig()
