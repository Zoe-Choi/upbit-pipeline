"""
Upbit Data Pipeline - Real-time cryptocurrency data collection and processing.

This package provides:
- WebSocket client for Upbit real-time data
- Kafka producer for message streaming
- Data models for ticker, trade, and orderbook data
- Configuration management
"""

__version__ = "1.0.0"
__author__ = "Data Engineering Team"

from src.config import get_config, AppConfig
from src.exceptions import PipelineError, ValidationError, ConnectionError

__all__ = [
    "get_config",
    "AppConfig",
    "PipelineError",
    "ValidationError",
    "ConnectionError",
    "__version__",
]
