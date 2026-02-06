"""
Custom exceptions for the Upbit pipeline.

Follows the principle of creating specific, meaningful exception types
that provide clear context about what went wrong.
"""
from typing import Any, Dict, Optional


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# =============================================================================
# Data Validation Errors
# =============================================================================


class ValidationError(PipelineError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        expected: Optional[str] = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]  # Truncate for safety
        if expected:
            details["expected"] = expected

        super().__init__(message, details)
        self.field = field
        self.value = value
        self.expected = expected


class MissingFieldError(ValidationError):
    """Raised when a required field is missing."""

    def __init__(self, field: str, data: Optional[Dict[str, Any]] = None):
        message = f"Required field '{field}' is missing"
        super().__init__(message, field=field)
        self.available_fields = list(data.keys()) if data else []


class InvalidTypeError(ValidationError):
    """Raised when a field has an invalid type."""

    def __init__(self, field: str, expected_type: str, actual_value: Any):
        actual_type = type(actual_value).__name__
        message = f"Field '{field}' has invalid type: expected {expected_type}, got {actual_type}"
        super().__init__(
            message,
            field=field,
            value=actual_value,
            expected=expected_type,
        )


class InvalidValueError(ValidationError):
    """Raised when a field has an invalid value."""

    def __init__(self, field: str, value: Any, reason: str):
        message = f"Invalid value for field '{field}': {reason}"
        super().__init__(message, field=field, value=value)
        self.reason = reason


# =============================================================================
# Connection Errors
# =============================================================================


class ConnectionError(PipelineError):
    """Base class for connection-related errors."""

    pass


class WebSocketError(ConnectionError):
    """Raised when WebSocket connection fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        reconnect_count: int = 0,
    ):
        details = {"reconnect_count": reconnect_count}
        if url:
            details["url"] = url
        super().__init__(message, details)
        self.url = url
        self.reconnect_count = reconnect_count


class WebSocketReconnectError(WebSocketError):
    """Raised when maximum reconnection attempts are exhausted."""

    def __init__(self, max_attempts: int, last_error: Optional[Exception] = None):
        message = f"Failed to reconnect after {max_attempts} attempts"
        super().__init__(message, reconnect_count=max_attempts)
        self.max_attempts = max_attempts
        self.last_error = last_error


class KafkaConnectionError(ConnectionError):
    """Raised when Kafka connection fails."""

    def __init__(
        self,
        message: str,
        bootstrap_servers: Optional[str] = None,
    ):
        details = {}
        if bootstrap_servers:
            details["bootstrap_servers"] = bootstrap_servers
        super().__init__(message, details)
        self.bootstrap_servers = bootstrap_servers


# =============================================================================
# Producer Errors
# =============================================================================


class ProducerError(PipelineError):
    """Base class for producer-related errors."""

    pass


class MessageSerializationError(ProducerError):
    """Raised when message serialization fails."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class MessageDeliveryError(ProducerError):
    """Raised when message delivery to Kafka fails."""

    def __init__(
        self,
        message: str,
        topic: Optional[str] = None,
        partition: Optional[int] = None,
        key: Optional[str] = None,
    ):
        details = {}
        if topic:
            details["topic"] = topic
        if partition is not None:
            details["partition"] = partition
        if key:
            details["key"] = key
        super().__init__(message, details)
        self.topic = topic
        self.partition = partition
        self.key = key


class BufferFullError(ProducerError):
    """Raised when the producer buffer is full."""

    def __init__(self, queue_size: int = 0):
        message = "Producer buffer is full"
        super().__init__(message, {"queue_size": queue_size})
        self.queue_size = queue_size


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(PipelineError):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, details)
        self.config_key = config_key
