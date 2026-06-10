import importlib.util
import io
import os
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(ROOT, "miners", "gpu_fingerprint_vulkan.py")


class TrackingFile(io.StringIO):
    def __init__(self, value):
        super().__init__(value)
        self.was_closed = False

    def close(self):
        self.was_closed = True
        super().close()


def load_module():
    fake_vk = types.SimpleNamespace()
    with patch.dict(sys.modules, {"vulkan": fake_vk}):
        spec = importlib.util.spec_from_file_location("gpu_fingerprint_vulkan", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class VulkanSystemProbeTests(unittest.TestCase):
    def test_system_probe_closes_sysfs_file_handles(self):
        module = load_module()
        opened = []

        def fake_open(path, *args, **kwargs):
            values = {
                "/sys/class/drm/card0/device/vendor": "0x1002\n",
                "/sys/class/drm/card0/device/device": "0x73bf\n",
                "/sys/class/drm/card0/device/hwmon/hwmon0/temp1_input": "42000\n",
            }
            handle = TrackingFile(values[path])
            opened.append(handle)
            return handle

        completed = subprocess.CompletedProcess(
            args=["lspci", "-v", "-s", ""],
            returncode=0,
            stdout="",
            stderr="",
        )

        with patch("subprocess.run", return_value=completed), \
             patch("glob.glob") as fake_glob, \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=fake_open):
            fake_glob.side_effect = [
                ["/sys/class/drm/card0/device/vendor"],
                ["/sys/class/drm/card0/device/hwmon/hwmon0/temp1_input"],
            ]

            result = module.channel_system_gpu_probe()

        self.assertTrue(result.passed)
        self.assertEqual(result.data["drm_cards"][0]["vendor"], "0x1002")
        self.assertEqual(result.data["drm_cards"][0]["device"], "0x73bf")
        self.assertEqual(result.data["card0_temp_c"], 42)
        self.assertEqual(len(opened), 3)
        self.assertTrue(all(handle.was_closed for handle in opened))


if __name__ == "__main__":
    unittest.main()
