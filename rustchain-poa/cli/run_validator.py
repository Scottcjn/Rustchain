import sys
from validator.validate_genesis import validate_genesis
import json

if len(sys.argv) != 2:
    print("Usage: python run_validator.py path/to/genesis.json")
    sys.exit(1)

result = validate_genesis(sys.argv[1])
print(json.dumps(result, indent=2))
