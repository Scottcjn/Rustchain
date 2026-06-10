import json

def parse_json_input(input_json):
    """Parses the given JSON string into a Python dictionary."""
    try:
        return json.loads(input_json)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON input: " + str(e))

from typing import Any

def safe_fromhex(hex_str: str, default: Any = None) -> Any:
    """
    Safely convert a hex string to bytes. 
    Returns 'default' if the input is not valid hex.
    """
    if not isinstance(hex_str, str):
        return default
    try:
        return bytes.fromhex(hex_str)
    except (ValueError, TypeError):
        return default
