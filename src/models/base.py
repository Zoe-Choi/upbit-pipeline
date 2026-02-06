"""
Base classes and protocols for data models.

Implements the Template Method pattern for common operations
and provides a consistent interface across all message types.

Performance optimizations:
- All imports at module level (avoid per-call lookup overhead)
- time.time_ns() instead of datetime.now() for ingestion timestamp
- Cached property patterns where applicable
"""
import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, TypeVar

from src.exceptions import MissingFieldError, InvalidTypeError, InvalidValueError

T = TypeVar("T")


class BaseMessage(ABC):
    """
    Abstract base class for all WebSocket messages.
    
    Provides common functionality for serialization, validation,
    and Kafka message formatting.
    """

    # Subclasses should define required fields
    REQUIRED_FIELDS: tuple = ()
    
    @classmethod
    @abstractmethod
    def from_websocket(cls, data: Dict[str, Any]) -> "BaseMessage":
        """
        Factory method to create instance from WebSocket data.
        
        Args:
            data: Raw WebSocket message dictionary
            
        Returns:
            Instance of the message class
            
        Raises:
            MissingFieldError: If required field is missing
            InvalidTypeError: If field has wrong type
        """
        pass

    @classmethod
    def _validate_required_fields(cls, data: Dict[str, Any]) -> None:
        """
        Validate that all required fields are present.
        
        Args:
            data: Data dictionary to validate
            
        Raises:
            MissingFieldError: If any required field is missing
        """
        for field in cls.REQUIRED_FIELDS:
            if field not in data:
                raise MissingFieldError(field, data)

    @classmethod
    def _extract_market(cls, data: Dict[str, Any]) -> str:
        """
        Extract market code from data (handles 'market' or 'code' field).
        
        Args:
            data: Data dictionary
            
        Returns:
            Market code string
            
        Raises:
            MissingFieldError: If neither 'market' nor 'code' field exists
        """
        market = data.get("market") or data.get("code")
        if not market:
            raise MissingFieldError("market", data)
        return str(market)

    @classmethod
    def _safe_float(cls, value: Any, field: str, default: float = 0.0) -> float:
        """
        Safely convert value to float.
        
        Args:
            value: Value to convert
            field: Field name for error messages
            default: Default value if None
            
        Returns:
            Float value
            
        Raises:
            InvalidTypeError: If conversion fails
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError) as e:
            raise InvalidTypeError(field, "float", value) from e

    @classmethod
    def _safe_int(cls, value: Any, field: str, default: int = 0) -> int:
        """
        Safely convert value to int.
        
        Args:
            value: Value to convert
            field: Field name for error messages
            default: Default value if None
            
        Returns:
            Integer value
            
        Raises:
            InvalidTypeError: If conversion fails
        """
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError) as e:
            raise InvalidTypeError(field, "int", value) from e

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert instance to dictionary.
        
        Returns:
            Dictionary representation with enum values converted to strings
        """
        result = asdict(self)
        return self._convert_enums(result)

    def _convert_enums(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert enum values to their string representation.
        
        Override in subclasses for specific enum handling.
        """
        return data

    def to_json(self) -> str:
        """
        Serialize to JSON string.
        
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_kafka_message(self) -> Dict[str, Any]:
        """
        Convert to Kafka message format with metadata.
        
        Adds ingestion timestamp and source information
        for data lineage tracking.
        
        Performance: Uses time.time_ns() instead of datetime.now()
        for ~10x faster timestamp generation.
        
        Returns:
            Dictionary ready for Kafka serialization
        """
        data = self.to_dict()
        data["_metadata"] = {
            "ingested_at_ns": time.time_ns(),
            "source": "upbit_websocket",
            "version": "1.0",
        }
        return data

    @property
    def market(self) -> str:
        """Market code (e.g., 'KRW-BTC')."""
        raise NotImplementedError

    @property
    def symbol(self) -> str:
        """
        Extract symbol from market code.
        
        Example: 'KRW-BTC' -> 'BTC'
        """
        market = self.market
        return market.split("-")[1] if "-" in market else market

    @property
    def quote_currency(self) -> str:
        """
        Extract quote currency from market code.
        
        Example: 'KRW-BTC' -> 'KRW'
        """
        market = self.market
        return market.split("-")[0] if "-" in market else "KRW"


class MessageValidator:
    """
    Utility class for validating message data.
    
    Provides composable validation methods that can be chained together.
    
    Performance notes:
    - All exception imports at module level
    - Uses time.time() instead of datetime.now() for timestamp validation
    """
    
    # Cache for timestamp range (updated every second)
    _timestamp_cache_time: float = 0
    _timestamp_range: tuple = (0, 0)

    @staticmethod
    def validate_positive(value: float, field: str) -> float:
        """Validate that value is positive."""
        if value < 0:
            raise InvalidValueError(field, value, "must be positive")
        return value

    @staticmethod
    def validate_not_empty(value: str, field: str) -> str:
        """Validate that string is not empty."""
        if not value or not value.strip():
            raise InvalidValueError(field, value, "must not be empty")
        return value

    @staticmethod
    def validate_market_format(market: str) -> str:
        """
        Validate market code format (e.g., 'KRW-BTC').
        
        Args:
            market: Market code to validate
            
        Returns:
            Validated market code
            
        Raises:
            InvalidValueError: If format is invalid
        """
        if not market or "-" not in market:
            raise InvalidValueError(
                "market",
                market,
                "must be in format 'QUOTE-BASE' (e.g., 'KRW-BTC')"
            )
        return market

    @classmethod
    def _get_timestamp_range(cls) -> tuple:
        """
        Get cached timestamp validation range.
        
        Updates cache every second for efficiency.
        """
        current_time = time.time()
        if current_time - cls._timestamp_cache_time >= 1.0:
            now_ms = current_time * 1000
            cls._timestamp_range = (
                now_ms - (365 * 24 * 60 * 60 * 1000),  # 1 year ago
                now_ms + (24 * 60 * 60 * 1000),        # 1 day future
            )
            cls._timestamp_cache_time = current_time
        return cls._timestamp_range

    @classmethod
    def validate_timestamp(cls, timestamp: int, field: str) -> int:
        """
        Validate timestamp is reasonable (within last year to now + 1 day).
        
        Performance: Uses cached range updated every second.
        
        Args:
            timestamp: Unix timestamp in milliseconds
            field: Field name for error messages
            
        Returns:
            Validated timestamp
        """
        one_year_ago, one_day_future = cls._get_timestamp_range()

        if not (one_year_ago <= timestamp <= one_day_future):
            raise InvalidValueError(
                field,
                timestamp,
                "timestamp out of reasonable range"
            )
        return timestamp
