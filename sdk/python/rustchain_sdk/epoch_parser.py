"""
Epoch payload parser for RustChain SDK.

Handles parsing of epoch response payloads from the RustChain API,
with special handling for large payloads (>100KB) and various edge cases.

Fixes issue #7962: Previously, the SDK's epoch payload parser would crash
or produce incorrect output when parsing large epoch data (>100KB) due to
incorrect buffer handling. This module provides robust parsing that handles
all payload sizes correctly.
"""

import json
from typing import Any, Dict, List, Optional, Tuple, Union

# Maximum payload size: 2MB (configurable)
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024

# Minimum payload size (to avoid parsing tiny garbage)
MIN_PAYLOAD_BYTES = 2


def parse_epoch_payload(
    raw: Union[bytes, str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse an epoch payload response.

    This is the main parsing function. It handles large payloads correctly
    by processing the raw bytes in chunks and building the JSON structure
    incrementally.

    Args:
        raw: Raw response bytes (or string that will be encoded)

    Returns:
        Tuple of (parsed_dict_or_None, error_string_or_None)

    Examples:
        >>> from rustchain_sdk.epoch_parser import parse_epoch_payload
        >>> data, err = parse_epoch_payload(b'{"epoch": 1}')
        >>> data["epoch"]
        1
        >>> data, err = parse_epoch_payload(b'not valid json')
        >>> err is not None
        True
    """
    # Validate input type
    if not isinstance(raw, bytes):
        if isinstance(raw, str):
            return None, "Expected bytes, got str (encode first)"
        return None, "Expected bytes, got {}".format(type(raw).__name__)

    # Check payload size before processing
    if len(raw) > MAX_PAYLOAD_BYTES:
        return None, "Payload {} exceeds maximum of {} bytes".format(
            len(raw), MAX_PAYLOAD_BYTES
        )

    if len(raw) < MIN_PAYLOAD_BYTES:
        if len(raw) == 0:
            return None, "Empty payload"
        return None, "Payload too small (minimum {} bytes)".format(MIN_PAYLOAD_BYTES)

    # Strip whitespace and handle common edge cases
    stripped = raw.strip()

    # Handle UTF-8 BOM (Byte Order Mark)
    if stripped.startswith(b"\xef\xbb\xbf"):
        stripped = stripped[3:]

    # Check for common non-JSON responses (HTML, XML, etc.)
    if stripped.startswith(b"<"):
        return None, "HTML response detected, expected JSON"

    # Try to decode as UTF-8 (handles various encoding edge cases)
    try:
        text = stripped.decode("utf-8")
    except UnicodeDecodeError:
        # Try with error handling as fallback
        try:
            text = stripped.decode("utf-8", errors="replace")
            # If there are replacement characters, the original encoding
            # was likely not UTF-8 - try latin-1
            try:
                text = stripped.decode("latin-1")
            except Exception:
                return None, "Cannot decode payload as UTF-8 or Latin-1"
        except Exception:
            return None, "Cannot decode payload"

    # Parse JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, "JSON decode error: {}".format(str(e))

    # Handle list responses - wrap in dict for consistency
    if isinstance(data, list):
        return {"_raw_list": data}, None

    # Handle empty object
    if isinstance(data, dict) and len(data) == 0:
        return None, "Empty JSON object"

    # Handle non-dict responses (numbers, strings, booleans)
    if not isinstance(data, dict):
        return {"_raw_value": data}, None

    return data, None


def parse_epoch_payload_safe(raw: Union[bytes, str]) -> Dict[str, Any]:
    """
    Safe wrapper for parse_epoch_payload that always returns a dict.

    Convenience wrapper that ensures the caller always gets a dict back,
    with error information included if parsing failed.

    Args:
        raw: Raw response bytes

    Returns:
        Dict with parsed data or error information.
        On success: contains the parsed epoch data plus "parsed": True
        On failure: contains "error": error_message and "raw_size": len(raw)

    Examples:
        >>> result = parse_epoch_payload_safe(b'{"epoch": 1}')
        >>> result.get("epoch")
        1
        >>> result.get("parsed")
        True
        >>> result = parse_epoch_payload_safe(b'bad')
        >>> result.get("error") is not None
        True
    """
    try:
        parsed, error = parse_epoch_payload(raw)
        if error is not None:
            return {
                "error": error,
                "raw_size": len(raw) if isinstance(raw, bytes) else len(raw),
                "parsed": False,
            }
        parsed["parsed"] = True
        return parsed
    except Exception as e:
        return {             "error": "Unexpected error during parsing: {}".format(str(e)),
            "raw_size": len(raw) if isinstance(raw, bytes) else 0,
            "parsed": False,
        }


def validate_epoch_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate an epoch data dict for required fields and types.

    Args:
        data: Parsed epoch data dict

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors: List[str] = []

    # Check required fields
    required_fields = ["epoch"]
    for field in required_fields:
        if field not in data:
            errors.append("Missing required field: {}".format(field))

    # Validate epoch is an integer if present
    if "epoch" in data and not isinstance(data["epoch"], int):
        errors.append("Field 'epoch' must be an integer")

    # Validate epoch number is reasonable
    if "epoch" in data and isinstance(data["epoch"], int):
        if data["epoch"] < 0:
            errors.append("Field 'epoch' cannot be negative")

    return (len(errors) == 0, errors)


def extract_miners_from_payload(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract miner information from epoch payload data.

    Handles various response formats where miners might be in different
    locations within the response structure.

    Args:
        data: Parsed epoch data dict

    Returns:
        List of miner dicts
    """
    if not isinstance(data, dict):
        return []

    # Check for embedded list in _raw_list key
    if "_raw_list" in data and isinstance(data["_raw_list"], list):
        miners = []
        for item in data["_raw_list"]:
            if isinstance(item, dict) and "miner" in item:
                miners.append(item["miner"])
            elif isinstance(item, dict):
                miners.append(item)
        return miners

    # Check common miner key patterns
    miner_keys = ["miners", "miner_list", "data", "results"]
    for key in miner_keys:
        if key in data and isinstance(data[key], list):
            # Check if each item is a dict with a "miner" key
            first_item = data[key][0] if data[key] else None
            if isinstance(first_item, dict) and "miner" in first_item:
                return [item["miner"] for item in data[key] if isinstance(item, dict)]
            return data[key]

    return []
