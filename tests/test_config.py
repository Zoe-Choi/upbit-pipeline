"""
Tests for configuration module.
"""
import os
import pytest
from unittest.mock import patch

from src.config import (
    AppConfig,
    UpbitConfig,
    KafkaConfig,
    MinioConfig,
    MarketConfig,
    get_config,
)


class TestKafkaConfig:
    """Tests for KafkaConfig."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = KafkaConfig()
        
        assert "localhost:29092" in config.bootstrap_servers
        assert config.topic_ticker == "upbit-ticker"
        assert config.acks == "all"
    
    def test_bootstrap_servers_list(self):
        """Test bootstrap servers as list."""
        config = KafkaConfig()
        servers = config.bootstrap_servers_list
        
        assert isinstance(servers, list)
        assert len(servers) > 0
    
    @patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": "broker1:9092,broker2:9092"})
    def test_env_override(self):
        """Test environment variable override."""
        # Need to create new instance to pick up env var
        config = KafkaConfig()
        
        assert "broker1:9092" in config.bootstrap_servers


class TestMarketConfig:
    """Tests for MarketConfig."""
    
    def test_default_markets(self):
        """Test default market list."""
        config = MarketConfig()
        
        assert "KRW-BTC" in config.default_markets
        assert "KRW-ETH" in config.default_markets
    
    @patch.dict(os.environ, {"UPBIT_MARKETS": "KRW-BTC,KRW-XRP"})
    def test_from_env(self):
        """Test loading markets from environment."""
        config = MarketConfig.from_env()
        
        assert len(config.default_markets) == 2
        assert "KRW-BTC" in config.default_markets
        assert "KRW-XRP" in config.default_markets


class TestAppConfig:
    """Tests for AppConfig."""
    
    def test_nested_configs(self):
        """Test nested configuration objects."""
        config = AppConfig()
        
        assert isinstance(config.upbit, UpbitConfig)
        assert isinstance(config.kafka, KafkaConfig)
        assert isinstance(config.minio, MinioConfig)
        assert isinstance(config.markets, MarketConfig)
    
    def test_get_config_singleton(self):
        """Test singleton pattern."""
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
