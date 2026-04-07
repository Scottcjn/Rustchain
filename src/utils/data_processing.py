import json

def parse_json_input(input_json):
    """Parses the given JSON string into a Python dictionary."""
    try:
        return json.loads(input_json)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON input: " + str(e))
