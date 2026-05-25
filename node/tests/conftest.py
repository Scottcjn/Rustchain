"""Test configuration — adds node/ to Python path for sibling module imports."""
import sys
from pathlib import Path

# Add parent directory (node/) to sys.path so tests can import sibling modules
# like bottube_feed from bottube_feed_routes
tests_dir = Path(__file__).parent
node_dir = tests_dir.parent
if str(node_dir) not in sys.path:
    sys.path.insert(0, str(node_dir))
