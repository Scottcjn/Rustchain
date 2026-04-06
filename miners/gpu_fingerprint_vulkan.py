#!/usr/bin/env python3
"""
GPU Fingerprint (Vulkan) — PPA Channel 8 for non-CUDA GPUs
===========================================================

Fingerprints AMD, Intel, and other GPUs that don't support CUDA/PyTorch
by using Vulkan compute for timing measurements and system probes for
device identification.

This complements gpu_fingerprint.py (CUDA/PyTorch) for full PPA coverage
across all GPU vendors.

Usage:
    python3 gpu_fingerprint_vulkan.py [--device 1]  # 0=NVIDIA, 1=AMD iGPU, etc.
"""

import hashlib
import json
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field

try:
    import vulkan as vk
except ImportError:
    print("ERROR: vulkan module required. Install: pip install vulkan")
    sys.exit(1)


@dataclass
class VulkanGPUFingerprint:
    gpu_name: str
    gpu_index: int
    device_type: str
    vendor_id: str
    vram_mb: int
    api_version: str
    channels: list = field(default_factory=list)
    all_passed: bool = False
    fingerprint_hash: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class ChannelResult:
    name: str
    passed: bool
    data: dict = field(default_factory=dict)
    notes: str = ""


def _get_vulkan_devices():
    """Enumerate Vulkan physical devices."""
    app_info = vk.VkApplicationInfo(
        pApplicationName="PPA-Vulkan",
        applicationVersion=vk.VK_MAKE_VERSION(1, 0, 0),
        apiVersion=vk.VK_API_VERSION_1_0,
    )
    inst_info = vk.VkInstanceCreateInfo(pApplicationInfo=app_info)
    instance = vk.vkCreateInstance(inst_info, None)
    devices = vk.vkEnumeratePhysicalDevices(instance)
    return instance, devices


def _get_device_info(device):
    """Get device properties and memory info."""
    props = vk.vkGetPhysicalDeviceProperties(device)
    mem = vk.vkGetPhysicalDeviceMemoryProperties(device)

    total_vram = 0
    for j in range(mem.memoryHeapCount):
        heap = mem.memoryHeaps[j]
        if heap.flags & vk.VK_MEMORY_HEAP_DEVICE_LOCAL_BIT:
            total_vram += heap.size

    type_map = {0: "OTHER", 1: "INTEGRATED", 2: "DISCRETE", 3: "VIRTUAL", 4: "CPU"}
    return {
        "name": props.deviceName,
        "type": type_map.get(props.deviceType, "UNKNOWN"),
        "vendor_id": hex(props.vendorID),
        "vram_mb": total_vram // (1024 * 1024),
        "driver_version": props.driverVersion,
        "api_major": vk.VK_VERSION_MAJOR(props.apiVersion),
        "api_minor": vk.VK_VERSION_MINOR(props.apiVersion),
        "limits": {
            "max_compute_work_group_count": [
                props.limits.maxComputeWorkGroupCount[i] for i in range(3)
            ],
            "max_compute_work_group_size": [
                props.limits.maxComputeWorkGroupSize[i] for i in range(3)
            ],
            "max_compute_work_group_invocations": props.limits.maxComputeWorkGroupInvocations,
            "max_memory_allocation_count": props.limits.maxMemoryAllocationCount,
            "timestamp_period": props.limits.timestampPeriod,
        },
    }


def channel_vulkan_identity(device_info: dict) -> ChannelResult:
    """Channel 8v-a: Vulkan device identity and limits fingerprint."""
    limits = device_info["limits"]

    # The combination of limits is architecture-specific
    identity_str = (
        f"{device_info['name']}|{device_info['vendor_id']}|"
        f"{device_info['type']}|{device_info['vram_mb']}|"
        f"wg:{limits['max_compute_work_group_invocations']}|"
        f"ts:{limits['timestamp_period']}"
    )
    identity_hash = hashlib.sha256(identity_str.encode()).hexdigest()[:16]

    # Timestamp period is silicon-specific — varies by GPU clock
    ts_period = limits["timestamp_period"]

    passed = len(device_info["name"]) > 0 and ts_period > 0
    return ChannelResult(
        name="8v-a: Vulkan Device Identity",
        passed=passed,
        data={
            "gpu_name": device_info["name"],
            "vendor": device_info["vendor_id"],
            "device_type": device_info["type"],
            "vram_mb": device_info["vram_mb"],
            "timestamp_period_ns": ts_period,
            "max_workgroup_invocations": limits["max_compute_work_group_invocations"],
            "identity_hash": identity_hash,
        },
        notes=f"{device_info['name']} ({device_info['type']}, {device_info['vram_mb']}MB, ts={ts_period:.1f}ns)",
    )


def channel_vulkan_queue_families(device) -> ChannelResult:
    """Channel 8v-b: Queue family configuration fingerprint."""
    families = vk.vkGetPhysicalDeviceQueueFamilyProperties(device)

    family_data = []
    compute_queues = 0
    graphics_queues = 0
    transfer_queues = 0

    for i, fam in enumerate(families):
        flags = []
        if fam.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT:
            flags.append("GRAPHICS")
            graphics_queues += fam.queueCount
        if fam.queueFlags & vk.VK_QUEUE_COMPUTE_BIT:
            flags.append("COMPUTE")
            compute_queues += fam.queueCount
        if fam.queueFlags & vk.VK_QUEUE_TRANSFER_BIT:
            flags.append("TRANSFER")
            transfer_queues += fam.queueCount

        family_data.append({
            "index": i,
            "flags": flags,
            "count": fam.queueCount,
            "timestamp_valid_bits": fam.timestampValidBits,
        })

    # Queue family layout is architecture-specific
    queue_hash = hashlib.sha256(
        json.dumps(family_data, sort_keys=True).encode()
    ).hexdigest()[:16]

    passed = compute_queues > 0
    return ChannelResult(
        name="8v-b: Queue Family Configuration",
        passed=passed,
        data={
            "families": family_data,
            "total_compute_queues": compute_queues,
            "total_graphics_queues": graphics_queues,
            "total_transfer_queues": transfer_queues,
            "queue_hash": queue_hash,
        },
        notes=f"{len(family_data)} families, {compute_queues} compute queues, {graphics_queues} graphics queues",
    )


def channel_vulkan_memory_types(device) -> ChannelResult:
    """Channel 8v-c: Memory type configuration fingerprint."""
    mem = vk.vkGetPhysicalDeviceMemoryProperties(device)

    heaps = []
    for i in range(mem.memoryHeapCount):
        heap = mem.memoryHeaps[i]
        heaps.append({
            "index": i,
            "size_mb": heap.size // (1024 * 1024),
            "device_local": bool(heap.flags & vk.VK_MEMORY_HEAP_DEVICE_LOCAL_BIT),
        })

    types = []
    for i in range(mem.memoryTypeCount):
        mt = mem.memoryTypes[i]
        flags = []
        if mt.propertyFlags & vk.VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT:
            flags.append("DEVICE_LOCAL")
        if mt.propertyFlags & vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT:
            flags.append("HOST_VISIBLE")
        if mt.propertyFlags & vk.VK_MEMORY_PROPERTY_HOST_COHERENT_BIT:
            flags.append("HOST_COHERENT")
        if mt.propertyFlags & vk.VK_MEMORY_PROPERTY_HOST_CACHED_BIT:
            flags.append("HOST_CACHED")
        types.append({
            "index": i,
            "heap_index": mt.heapIndex,
            "flags": flags,
        })

    # Memory layout is architecture-specific — iGPU vs dGPU very different
    mem_hash = hashlib.sha256(
        json.dumps({"heaps": heaps, "types": types}, sort_keys=True).encode()
    ).hexdigest()[:16]

    passed = len(heaps) > 0
    return ChannelResult(
        name="8v-c: Memory Type Configuration",
        passed=passed,
        data={
            "heap_count": len(heaps),
            "heaps": heaps,
            "type_count": len(types),
            "types": types,
            "memory_hash": mem_hash,
        },
        notes=f"{len(heaps)} heaps, {len(types)} memory types, hash={mem_hash}",
    )


def channel_system_gpu_probe() -> ChannelResult:
    """Channel 8v-d: System-level GPU probe (lspci, driver info)."""
    data = {}

    # lspci GPU info
    try:
        result = subprocess.run(
            ["lspci", "-v", "-s", ""],
            capture_output=True, text=True, timeout=5
        )
        gpu_lines = []
        for line in result.stdout.splitlines():
            if any(k in line.lower() for k in ["vga", "display", "3d controller", "radeon", "amd", "nvidia", "intel"]):
                gpu_lines.append(line.strip())
        data["lspci_gpus"] = gpu_lines[:10]
    except Exception:
        data["lspci_gpus"] = []

    # DRM info
    try:
        import glob
        drm_cards = sorted(glob.glob("/sys/class/drm/card*/device/vendor"))
        drm_info = []
        for vendor_path in drm_cards:
            card = vendor_path.split("/")[4]
            vendor = open(vendor_path).read().strip()
            device_path = vendor_path.replace("vendor", "device")
            device = open(device_path).read().strip() if __import__("os").path.exists(device_path) else "unknown"
            drm_info.append({"card": card, "vendor": vendor, "device": device})
        data["drm_cards"] = drm_info
    except Exception:
        data["drm_cards"] = []

    # AMDGPU-specific info
    try:
        import glob
        amd_hwmon = glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/temp1_input")
        for path in amd_hwmon:
            card = path.split("/")[4]
            temp = int(open(path).read().strip()) // 1000
            data[f"{card}_temp_c"] = temp
    except Exception:
        pass

    probe_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
    data["probe_hash"] = probe_hash

    passed = len(data.get("drm_cards", [])) > 0 or len(data.get("lspci_gpus", [])) > 0
    return ChannelResult(
        name="8v-d: System GPU Probe",
        passed=passed,
        data=data,
        notes=f"{len(data.get('drm_cards', []))} DRM cards, {len(data.get('lspci_gpus', []))} lspci GPUs",
    )


def run_vulkan_fingerprint(device_index: int = 0) -> VulkanGPUFingerprint:
    """Run all Vulkan GPU fingerprint channels."""
    instance, devices = _get_vulkan_devices()

    # Filter to non-CPU devices
    real_devices = []
    for dev in devices:
        props = vk.vkGetPhysicalDeviceProperties(dev)
        if props.deviceType != 4:  # Skip CPU (llvmpipe)
            real_devices.append(dev)

    if device_index >= len(real_devices):
        print(f"ERROR: Device index {device_index} out of range. {len(real_devices)} GPUs found.")
        vk.vkDestroyInstance(instance, None)
        sys.exit(1)

    device = real_devices[device_index]
    info = _get_device_info(device)

    print(f"\n{'='*60}")
    print(f"  GPU Fingerprint (Vulkan) — PPA Channel 8v")
    print(f"  Device: {info['name']}")
    print(f"  Type: {info['type']} | Vendor: {info['vendor_id']} | VRAM: {info['vram_mb']} MB")
    print(f"{'='*60}\n")

    channels = []

    # 8v-a: Identity
    print("[8v-a/4] Vulkan Device Identity...", end=" ", flush=True)
    ch_a = channel_vulkan_identity(info)
    print(f"{'PASS' if ch_a.passed else 'FAIL'}")
    print(f"         {ch_a.notes}")
    channels.append(ch_a)

    # 8v-b: Queue families
    print("[8v-b/4] Queue Family Configuration...", end=" ", flush=True)
    ch_b = channel_vulkan_queue_families(device)
    print(f"{'PASS' if ch_b.passed else 'FAIL'}")
    print(f"         {ch_b.notes}")
    channels.append(ch_b)

    # 8v-c: Memory types
    print("[8v-c/4] Memory Type Configuration...", end=" ", flush=True)
    ch_c = channel_vulkan_memory_types(device)
    print(f"{'PASS' if ch_c.passed else 'FAIL'}")
    print(f"         {ch_c.notes}")
    channels.append(ch_c)

    # 8v-d: System probe
    print("[8v-d/4] System GPU Probe...", end=" ", flush=True)
    ch_d = channel_system_gpu_probe()
    print(f"{'PASS' if ch_d.passed else 'FAIL'}")
    print(f"         {ch_d.notes}")
    channels.append(ch_d)

    all_passed = all(ch.passed for ch in channels)
    composite = json.dumps({ch.name: ch.data for ch in channels}, sort_keys=True)
    fingerprint_hash = hashlib.sha256(composite.encode()).hexdigest()

    print(f"\n{'='*60}")
    print(f"  RESULT: {'ALL CHANNELS PASSED' if all_passed else 'SOME CHANNELS FAILED'}")
    print(f"  Fingerprint: {fingerprint_hash[:32]}...")
    print(f"  Passed: {sum(1 for ch in channels if ch.passed)}/4")
    print(f"{'='*60}\n")

    type_map = {0: "OTHER", 1: "INTEGRATED", 2: "DISCRETE", 3: "VIRTUAL", 4: "CPU"}
    vk.vkDestroyInstance(instance, None)

    return VulkanGPUFingerprint(
        gpu_name=info["name"],
        gpu_index=device_index,
        device_type=info["type"],
        vendor_id=info["vendor_id"],
        vram_mb=info["vram_mb"],
        api_version=f"{info['api_major']}.{info['api_minor']}",
        channels=[asdict(ch) for ch in channels],
        all_passed=all_passed,
        fingerprint_hash=fingerprint_hash,
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GPU Fingerprint (Vulkan) — PPA Channel 8v")
    parser.add_argument("--device", type=int, default=0, help="Vulkan device index (0=first GPU, 1=second, etc.)")
    parser.add_argument("--list", action="store_true", help="List available Vulkan devices")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    if args.list:
        instance, devices = _get_vulkan_devices()
        for i, dev in enumerate(devices):
            info = _get_device_info(dev)
            skip = " (CPU - skipped)" if info["type"] == "CPU" else ""
            print(f"  [{i}] {info['name']} ({info['type']}, {info['vram_mb']}MB){skip}")
        vk.vkDestroyInstance(instance, None)
        sys.exit(0)

    fp = run_vulkan_fingerprint(device_index=args.device)

    if args.json:
        print(json.dumps(fp.to_dict(), indent=2))
