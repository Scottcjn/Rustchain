#!/usr/bin/env python3
"""RustChain Hardware Inventory — Scan and catalog vintage mining hardware."""
import json, urllib.request, os, platform, subprocess

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def detect_local():
    info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "arch": platform.architecture()[0],
    }
    try:
        if platform.system() == "Darwin":
            info["model"] = subprocess.check_output(["sysctl", "-n", "hw.model"], text=True).strip()
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info["cpu_model"] = line.split(":")[1].strip()
                        break
    except: pass
    
    # Estimate antiquity multiplier
    arch = info.get("machine", "").lower()
    if "ppc" in arch or "powerpc" in arch:
        info["estimated_multiplier"] = "2.5x (PowerPC)"
    elif "arm" in arch or "aarch64" in arch:
        info["estimated_multiplier"] = "1.0x (ARM)"
    else:
        info["estimated_multiplier"] = "1.0x (x86)"
    
    return info

def network_inventory():
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        r = urllib.request.urlopen(f"{NODE}/api/miners", timeout=10, context=ctx)
        miners = json.loads(r.read())
    except: miners = []
    
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    
    inventory = {}
    for m in miner_list:
        hw = m.get("hardware", m.get("cpu_arch", "unknown"))
        inventory[hw] = inventory.get(hw, 0) + 1
    
    return inventory

def main():
    print("RustChain Hardware Inventory")
    print("=" * 50)
    
    local = detect_local()
    print("\nLocal Machine:")
    for k, v in local.items():
        print(f"  {k}: {v}")
    
    print("\nNetwork Hardware Distribution:")
    inv = network_inventory()
    for hw, count in sorted(inv.items(), key=lambda x: -x[1]):
        print(f"  {hw}: {count} miner(s)")

if __name__ == "__main__":
    main()
