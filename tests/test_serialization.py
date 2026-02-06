"""
Tests for serialization utilities.

Comprehensive tests for JSON serialization/deserialization
used in Kafka message production and consumption.
"""
import json
import pytest
from typing import Dict, Any

from src.utils.serialization import (
    JSONSerializer,
    JSONDeserializer,
    create_key_serializer,
)


class TestJSONSerializer:
    """Tests for JSONSerializer class."""

    def test_serialize_simple_dict(self):
        """Test serialization of simple dictionary."""
        serializer = JSONSerializer()
        data = {"key": "value", "number": 123}

        result = serializer(data)

        assert isinstance(result, bytes)
        assert b'"key"' in result
        assert b'"value"' in result

    def test_serialize_nested_dict(self):
        """Test serialization of nested dictionary."""
        serializer = JSONSerializer()
        data = {
            "level1": {
                "level2": {
                    "value": "deep"
                }
            }
        }

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["level1"]["level2"]["value"] == "deep"

    def test_serialize_with_unicode(self):
        """Test serialization of unicode characters."""
        serializer = JSONSerializer()
        data = {"message": "한글 테스트", "emoji": "🚀"}

        result = serializer(data)

        # Should preserve unicode without escaping
        assert "한글 테스트".encode("utf-8") in result

    def test_serialize_none_returns_none(self):
        """Test that None input returns None."""
        serializer = JSONSerializer()
        result = serializer(None)

        assert result is None

    def test_serialize_with_numbers(self):
        """Test serialization of various number types."""
        serializer = JSONSerializer()
        data = {
            "int": 42,
            "float": 3.14159,
            "negative": -100,
            "large": 999999999999999,
            "small_float": 0.0000001,
        }

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["int"] == 42
        assert abs(parsed["float"] - 3.14159) < 0.00001
        assert parsed["negative"] == -100

    def test_serialize_with_boolean(self):
        """Test serialization of boolean values."""
        serializer = JSONSerializer()
        data = {"true_val": True, "false_val": False}

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["true_val"] is True
        assert parsed["false_val"] is False

    def test_serialize_with_list(self):
        """Test serialization of lists."""
        serializer = JSONSerializer()
        data = {"items": [1, 2, 3, "four", {"five": 5}]}

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert len(parsed["items"]) == 5
        assert parsed["items"][3] == "four"
        assert parsed["items"][4]["five"] == 5

    def test_serialize_empty_dict(self):
        """Test serialization of empty dictionary."""
        serializer = JSONSerializer()
        data: Dict[str, Any] = {}

        result = serializer(data)

        assert result == b"{}"

    def test_serialize_with_null_values(self):
        """Test serialization of None values in dict."""
        serializer = JSONSerializer()
        data = {"present": "value", "missing": None}

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["present"] == "value"
        assert parsed["missing"] is None

    def test_serialize_ticker_like_message(self):
        """Test serialization of a realistic ticker message."""
        serializer = JSONSerializer()
        data = {
            "market": "KRW-BTC",
            "trade_price": 50000000.0,
            "change": "RISE",
            "timestamp": 1707984000123,
            "_metadata": {
                "ingested_at": "2024-02-15T12:00:00Z",
                "source": "upbit_websocket",
            }
        }

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["market"] == "KRW-BTC"
        assert parsed["_metadata"]["source"] == "upbit_websocket"


class TestJSONDeserializer:
    """Tests for JSONDeserializer class."""

    def test_deserialize_simple_dict(self):
        """Test deserialization of simple JSON."""
        deserializer = JSONDeserializer()
        data = b'{"key": "value", "number": 123}'

        result = deserializer(data)

        assert result["key"] == "value"
        assert result["number"] == 123

    def test_deserialize_none_returns_none(self):
        """Test that None input returns None."""
        deserializer = JSONDeserializer()
        result = deserializer(None)

        assert result is None

    def test_deserialize_unicode(self):
        """Test deserialization of unicode content."""
        deserializer = JSONDeserializer()
        data = '{"message": "한글 테스트"}'.encode("utf-8")

        result = deserializer(data)

        assert result["message"] == "한글 테스트"

    def test_deserialize_nested_structure(self):
        """Test deserialization of nested JSON."""
        deserializer = JSONDeserializer()
        data = b'{"level1": {"level2": {"value": "deep"}}}'

        result = deserializer(data)

        assert result["level1"]["level2"]["value"] == "deep"

    def test_deserialize_invalid_json_raises_error(self):
        """Test that invalid JSON raises an error."""
        deserializer = JSONDeserializer()
        invalid_json = b'{"unclosed": '

        with pytest.raises(json.JSONDecodeError):
            deserializer(invalid_json)

    def test_roundtrip_serialization(self):
        """Test that serialize -> deserialize preserves data."""
        serializer = JSONSerializer()
        deserializer = JSONDeserializer()

        original = {
            "market": "KRW-BTC",
            "trade_price": 50000000.0,
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }

        serialized = serializer(original)
        deserialized = deserializer(serialized)

        assert deserialized == original


class TestKeySerializer:
    """Tests for key serializer function."""

    def test_serialize_simple_key(self):
        """Test serialization of simple string key."""
        serialize_key = create_key_serializer()

        result = serialize_key("KRW-BTC")

        assert result == b"KRW-BTC"

    def test_serialize_none_returns_none(self):
        """Test that None key returns None."""
        serialize_key = create_key_serializer()

        result = serialize_key(None)

        assert result is None

    def test_serialize_unicode_key(self):
        """Test serialization of unicode key."""
        serialize_key = create_key_serializer()

        result = serialize_key("키-값")

        assert result == "키-값".encode("utf-8")

    def test_serialize_empty_string(self):
        """Test serialization of empty string."""
        serialize_key = create_key_serializer()

        result = serialize_key("")

        assert result == b""


class TestSerializationPerformance:
    """Performance-related tests for serialization."""

    def test_serialize_large_message(self):
        """Test serialization of large message."""
        serializer = JSONSerializer()

        # Create a large message with many orderbook units
        data = {
            "market": "KRW-BTC",
            "timestamp": 1707984000123,
            "orderbook_units": [
                {
                    "ask_price": 50000000.0 + i,
                    "bid_price": 49999999.0 - i,
                    "ask_size": float(i),
                    "bid_size": float(i),
                }
                for i in range(100)
            ]
        }

        result = serializer(data)

        assert isinstance(result, bytes)
        parsed = json.loads(result.decode("utf-8"))
        assert len(parsed["orderbook_units"]) == 100

    def test_serialize_many_messages(self):
        """Test serialization of many messages (basic stress test)."""
        serializer = JSONSerializer()

        messages = [
            {"market": f"KRW-COIN{i}", "price": i * 1000}
            for i in range(1000)
        ]

        results = [serializer(msg) for msg in messages]

        assert len(results) == 1000
        assert all(isinstance(r, bytes) for r in results)


class TestSerializationEdgeCases:
    """Edge case tests for serialization."""

    def test_serialize_special_float_values(self):
        """Test handling of special float values."""
        serializer = JSONSerializer()

        # Note: JSON doesn't support Infinity or NaN
        # This should work with normal floats
        data = {"zero": 0.0, "negative_zero": -0.0}

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["zero"] == 0.0

    def test_serialize_deeply_nested(self):
        """Test serialization of deeply nested structure."""
        serializer = JSONSerializer()

        # Create deeply nested structure
        data: Dict[str, Any] = {"level": 0}
        current = data
        for i in range(50):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["level"] == 0
        assert "nested" in parsed

    def test_serialize_with_special_characters(self):
        """Test serialization with special characters in strings."""
        serializer = JSONSerializer()
        data = {
            "quotes": 'He said "hello"',
            "backslash": "path\\to\\file",
            "newline": "line1\nline2",
            "tab": "col1\tcol2",
        }

        result = serializer(data)
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["quotes"] == 'He said "hello"'
        assert parsed["backslash"] == "path\\to\\file"
        assert parsed["newline"] == "line1\nline2"
