import json
import sys
from pathlib import Path

POA_ROOT = Path(__file__).resolve().parents[1]
if str(POA_ROOT) not in sys.path:
    sys.path.insert(0, str(POA_ROOT))

from validator.validate_genesis import validate_genesis

if len(sys.argv) != 2:
    print("Usage: python run_validator.py path/to/genesis.json")
    sys.exit(1)

result = validate_genesis(sys.argv[1])
print(json.dumps(result, indent=2))
