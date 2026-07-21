"""
Regression test for the tensor-core compute-capability gate in gpu_attestation.

`GPUFingerprint.compute_capability` is a string built as f"{major}.{minor}"
("7.0", "8.0", "9.0", "10.0", "12.0", ...). get_gpu_attestation_payload gates
the Channel 8f (Tensor Core) fingerprint on that value being >= 7.0.

The gate used a raw string comparison (`fp.compute_capability >= "7.0"`), which
compares lexically: "10.0" >= "7.0" is False because '1' < '7'. That silently
dropped the tensor-core channel for exactly the newest tensor-core GPUs —
Blackwell data-center (CC 10.0) and consumer Blackwell / RTX-50 (CC 12.0) —
while Volta..Hopper (7.0-9.x) worked. The fix parses the value numerically.

This test does not require torch/CUDA: `import torch` in gpu_attestation is
function-local, so the module and the helper import cleanly on any host.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gpu_attestation import _supports_tensor_cores


def test_volta_through_hopper_supported():
    for cc in ["7.0", "7.5", "8.0", "8.6", "9.0"]:
        assert _supports_tensor_cores(cc) is True, cc


def test_blackwell_multidigit_major_supported():
    # These are exactly the values the old string comparison wrongly rejected.
    for cc in ["10.0", "12.0"]:
        assert _supports_tensor_cores(cc) is True, cc
        # Guard against a regression back to lexical comparison.
        assert (cc >= "7.0") is False, cc


def test_pre_volta_not_supported():
    for cc in ["5.0", "6.0", "6.1"]:
        assert _supports_tensor_cores(cc) is False, cc


def test_malformed_values_do_not_crash():
    for cc in [None, "", "abc"]:
        assert _supports_tensor_cores(cc) is False, cc
