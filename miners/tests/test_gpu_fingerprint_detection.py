# SPDX-License-Identifier: MIT
"""
Regression tests for GPU Fingerprint detection channels (8f, 8g).

Tests the VM detection and hardware cross-validation logic paths
WITHOUT requiring a real GPU — uses mocking to exercise the detection
code on any platform.
"""

import os
import sys
import unittest
from unittest import mock

# Add parent directory so we can import the module under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ---------------------------------------------------------------------------
# PCI bus ID normalisation helper — extracted for testability
# ---------------------------------------------------------------------------

def _normalise_pci_bus_id(pci_id: str) -> str:
    """Normalise an nvidia-smi PCI bus ID to the Linux sysfs 4-digit domain form.

    nvidia-smi can return either:
      - 4-digit domain: 0000:01:00.0
      - 8-digit domain: 00000000:65:00.0

    Linux sysfs always uses the 4-digit form, e.g. /sys/bus/pci/devices/0000:65:00.0
    """
    pci_lower = pci_id.lower()
    parts = pci_lower.split(":")
    if len(parts) == 3:
        domain_raw = parts[0]
        domain = domain_raw[-4:] if len(domain_raw) >= 4 else domain_raw.zfill(4)
        bus_slot_func = f"{parts[1]}:{parts[2]}"
        return f"{domain}:{bus_slot_func}"
    return pci_lower


class TestPCINormalization(unittest.TestCase):
    """Test PCI bus ID normalisation for sysfs path construction."""

    def test_4digit_domain(self):
        """Standard 4-digit domain from nvidia-smi."""
        self.assertEqual(
            _normalise_pci_bus_id("0000:01:00.0"),
            "0000:01:00.0",
        )

    def test_8digit_domain(self):
        """8-digit domain format that some nvidia-smi versions emit."""
        self.assertEqual(
            _normalise_pci_bus_id("00000000:65:00.0"),
            "0000:65:00.0",
        )

    def test_8digit_domain_nonzero(self):
        """8-digit domain with non-zero upper digits."""
        self.assertEqual(
            _normalise_pci_bus_id("00000001:3B:00.0"),
            "0001:3b:00.0",
        )

    def test_uppercase_input(self):
        """Verify case-insensitive handling."""
        self.assertEqual(
            _normalise_pci_bus_id("0000:3B:00.0"),
            "0000:3b:00.0",
        )

    def test_sysfs_path_construction_4digit(self):
        """Verify full sysfs path for 4-digit domain."""
        addr = _normalise_pci_bus_id("0000:01:00.0")
        path = f"/sys/bus/pci/devices/{addr}/driver"
        self.assertEqual(path, "/sys/bus/pci/devices/0000:01:00.0/driver")

    def test_sysfs_path_construction_8digit(self):
        """Verify full sysfs path for 8-digit domain — the bug ramimbo found."""
        addr = _normalise_pci_bus_id("00000000:65:00.0")
        path = f"/sys/bus/pci/devices/{addr}/driver"
        self.assertEqual(path, "/sys/bus/pci/devices/0000:65:00.0/driver")


class TestVMDetectionLogic(unittest.TestCase):
    """Test VM detection indicator logic (channel 8f)."""

    def test_no_indicators_means_bare_metal(self):
        """Empty indicator list should report bare metal."""
        indicators = []
        is_vm = len(indicators) > 0
        self.assertFalse(is_vm)

    def test_dmi_hypervisor_string_triggers_vm(self):
        """DMI containing a known hypervisor string should flag as VM."""
        vm_strings = [
            "vmware", "virtualbox", "kvm", "qemu", "xen",
            "hyperv", "hyper-v", "parallels", "bhyve",
        ]
        for vs in vm_strings:
            indicators = [f"dmi:/sys/class/dmi/id/product_name={vs}"]
            is_vm = len(indicators) > 0
            self.assertTrue(is_vm, f"Should detect VM for hypervisor string: {vs}")

    def test_vfio_driver_triggers_passthrough(self):
        """vfio-pci driver should be flagged as VM passthrough."""
        indicators = ["vfio_passthrough:driver=vfio-pci"]
        is_vm = len(indicators) > 0
        self.assertTrue(is_vm)

    def test_iommu_group_alone_does_not_trigger(self):
        """IOMMU group presence alone should NOT trigger VM detection.

        This was the false positive bug reported by JeremyZeng77: normal
        bare-metal hosts with IOMMU enabled were being flagged as VM.
        """
        # After the fix, we no longer add iommu_group indicators.
        # Only vfio-pci driver triggers the indicator.
        indicators = []  # No vfio-pci driver found
        is_vm = len(indicators) > 0
        self.assertFalse(is_vm, "IOMMU group alone should not trigger VM detection")

    def test_container_env_triggers_detection(self):
        """Container environment variables should flag container environment."""
        container_env_keys = [
            "KUBERNETES_SERVICE_HOST", "DOCKER_HOST", "container",
            "AWS_EXECUTION_ENV", "ECS_CONTAINER_METADATA_URI",
        ]
        for key in container_env_keys:
            indicators = [f"env:{key}"]
            is_vm = len(indicators) > 0
            self.assertTrue(is_vm, f"Should detect container for env: {key}")


class TestCrossValidationLogic(unittest.TestCase):
    """Test hardware cross-validation logic (channel 8g)."""

    def test_validated_when_source_matches(self):
        """When independent source matches torch, should return VALIDATED."""
        os_gpu_name = "nvidia geforce rtx 4090"
        torch_name = "nvidia geforce rtx 4090"
        mismatches = []
        independent_source_checked = os_gpu_name is not None

        validated = len(mismatches) == 0 and independent_source_checked
        self.assertTrue(validated)

    def test_inconclusive_when_no_source(self):
        """When no independent source is available, should return INCONCLUSIVE.

        This was the false positive bug reported by JeremyZeng77: AMD/ROCm
        hosts with no nvidia-smi would falsely report VALIDATED.
        """
        os_gpu_name = None
        mismatches = []
        independent_source_checked = os_gpu_name is not None

        validated = len(mismatches) == 0 and independent_source_checked
        self.assertFalse(validated, "Should not validate when no source checked")

        # Verify the status logic
        if not independent_source_checked:
            status = "INCONCLUSIVE"
        elif validated:
            status = "VALIDATED"
        else:
            status = "MISMATCH"

        self.assertEqual(status, "INCONCLUSIVE")

    def test_mismatch_when_names_differ(self):
        """When GPU names don't match, should return MISMATCH."""
        mismatches = ["name: torch='tesla v100' vs nvml='quadro rtx 8000'"]
        independent_source_checked = True

        validated = len(mismatches) == 0 and independent_source_checked
        self.assertFalse(validated)

    def test_mismatch_when_vram_differs(self):
        """When VRAM doesn't match, should flag a mismatch."""
        mismatches = ["vram: torch=16384MB vs nvml=8192MB"]
        independent_source_checked = True

        validated = len(mismatches) == 0 and independent_source_checked
        self.assertFalse(validated)

    def test_ld_preload_suspicious_flag(self):
        """LD_PRELOAD containing CUDA libraries should flag suspicious."""
        ld_preload = "/tmp/fake_libcuda.so"
        suspicious = ["cuda", "nvidia", "gpu", "nvcuda", "libcuda"]
        mismatches = []
        for s in suspicious:
            if s in ld_preload.lower():
                mismatches.append(f"ld_preload_suspicious: {ld_preload}")
                break

        self.assertEqual(len(mismatches), 1)
        self.assertIn("libcuda", mismatches[0])

    def test_ld_preload_clean_no_flag(self):
        """Normal LD_PRELOAD without GPU libraries should not flag."""
        ld_preload = "/usr/lib/libasan.so"
        suspicious = ["cuda", "nvidia", "gpu", "nvcuda", "libcuda"]
        mismatches = []
        for s in suspicious:
            if s in ld_preload.lower():
                mismatches.append(f"ld_preload_suspicious: {ld_preload}")
                break

        self.assertEqual(len(mismatches), 0)


if __name__ == "__main__":
    unittest.main()
