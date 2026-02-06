"""
Serialization utilities for Kafka messages.
"""
import json
from typing import Any, Dict, Callable

from confluent_kafka.serialization import SerializationContext, MessageField


class JSONSerializer:
    """JSON serializer for Kafka messages."""
    
    def __init__(self, schema: Dict[str, Any] = None):
        """
        Initialize serializer.
        
        Args:
            schema: Optional JSON schema for validation (not enforced)
        """
        self._schema = schema
    
    def __call__(
        self,
        obj: Dict[str, Any],
        ctx: SerializationContext = None,
    ) -> bytes:
        """
        Serialize object to JSON bytes.
        
        Args:
            obj: Dictionary to serialize
            ctx: Serialization context (unused)
            
        Returns:
            UTF-8 encoded JSON bytes
        """
        if obj is None:
            return None
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class JSONDeserializer:
    """JSON deserializer for Kafka messages."""
    
    def __call__(
        self,
        data: bytes,
        ctx: SerializationContext = None,
    ) -> Dict[str, Any]:
        """
        Deserialize JSON bytes to dictionary.
        
        Args:
            data: UTF-8 encoded JSON bytes
            ctx: Serialization context (unused)
            
        Returns:
            Deserialized dictionary
        """
        if data is None:
            return None
        return json.loads(data.decode("utf-8"))


def create_key_serializer() -> Callable[[str], bytes]:
    """Create a key serializer for market codes."""
    def serialize_key(key: str) -> bytes:
        if key is None:
            return None
        return key.encode("utf-8")
    return serialize_key
