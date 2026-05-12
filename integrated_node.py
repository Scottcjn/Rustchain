miners = {}

"""Test/import shim for the integrated RustChain node module.

This provides a stable import name (`integrated_node`) for tests while the
actual implementation file keeps its versioned filename.
"""

from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

_TARGET = Path(__file__).resolve().parent / "node" / "rustchain_v2_integrated_v2.2.1_rip200.py"
_spec = spec_from_file_location("rustchain_integrated_impl", _TARGET)
_mod = module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)

# Re-export public symbols
for _name in dir(_mod):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_mod, _name)
