"""
conftest.py — Local pytest configuration for the fuzz harness.

This file intentionally overrides the parent tests/conftest.py to prevent
the fuzz harness from trying to import the full 275 KB Flask server.
The fuzz harness is self-contained and only needs attestation_validators.py.
"""
# No fixtures needed — harness is fully self-contained.
