#!/usr/bin/env python3
"""
Enhanced Symplectic Miner — integrates WSL bridge + C loop.
Uses Windows PowerShell to detect real hardware (not WSL VM data),
then runs the symplectic-optimized mining loop with bytropix math.

Architecture:
  1. PowerShell bridge → real hardware serials/RAM/MACs
  2. Inject real HW data into miner attestation → 0.8x weight (not 1e-09)
  3. C symplectic loop schedules optimal attestation intervals
"""

import os, sys, json, subprocess, time, signal, atexit
from pathlib import Path

# Add tools to path
sys.path.insert(0, os.path.expanduser("~/rustchain/tools"))
from wsl_bridge import get_real_hardware_info, patch_miner_attestation

# Config
WALLET = "RTC17c0d21f04f6f65c1a85c0aeb5d4a305d57531096"
MINER_SCRIPT = os.path.expanduser("~/rustchain/miners/linux/rustchain_linux_miner.py")
C_LOOP_BIN = os.path.expanduser("~/rustchain/tools/symplectic_miner_loop")
LOG_DIR = Path.home() / ".rustchain" / "miner_logs"
HEARTBEAT_DIR = Path.home() / ".hermes" / "infra" / "heartbeats"
BASE_INTERVAL = 600  # 10 min
CYCLES_PER_SCHEDULE = 20

LOG_DIR.mkdir(parents=True, exist_ok=True)
HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)

running = True

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def heartbeat():
    hb = HEARTBEAT_DIR / "symplectic-miner.heartbeat"
    hb.write_text(str(int(time.time())))

def run_miner_cycle():
    """Run one attestation + enrollment cycle via the Python miner."""
    cmd = [sys.executable, MINER_SCRIPT, "--wallet", WALLET]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=720)
        output = result.stdout + result.stderr
        enrolled = "[OK] Enrolled!" in output
        attested = "[PASS] Attestation accepted!" in output
        balance = None
        for line in output.split("\n"):
            if "Balance:" in line and "RTC" in line:
                try:
                    balance = float(line.split("Balance:")[1].split("RTC")[0].strip())
                except: pass
        return {"enrolled": enrolled, "attested": attested, "balance": balance}
    except subprocess.TimeoutExpired:
        return {"enrolled": False, "attested": False, "balance": None, "error": "timeout"}
    except Exception as e:
        return {"enrolled": False, "attested": False, "balance": None, "error": str(e)}

def main():
    log("╔═══════════════════════════════════════════╗")
    log("║  Symplectic Miner v3 (WSL Bridge + C)    ║")
    log("║  Wallet: " + WALLET[:20] + "...                ║")
    log("╚═══════════════════════════════════════════╝")
    
    # Step 1: Get real hardware via PowerShell bridge
    log("Step 1: Detecting real hardware via PowerShell...")
    hw_info = get_real_hardware_info()
    if hw_info:
        log(f"  ✅ Model: {hw_info.get('model')}")
        log(f"  ✅ Serial: {hw_info.get('serial')}")
        log(f"  ✅ RAM: {hw_info.get('ram_gb')}GB")
        log(f"  ✅ CPU: {hw_info.get('cpu')}")
        log(f"  ✅ MACs: {hw_info.get('macs')}")
        # Save to file for the Python miner to read
        with open(os.path.expanduser("~/.rustchain/real_hardware.json"), "w") as f:
            json.dump(hw_info, f)
        log("  ✅ Real hardware data saved")
    else:
        log("  ⚠️  PowerShell unavailable — WSL probes only (1e-09 weight)")
    
    # Step 2: Verify C loop binary
    if os.path.exists(C_LOOP_BIN):
        log(f"Step 2: C symplectic loop ready ({os.path.getsize(C_LOOP_BIN)} bytes)")
    else:
        log("Step 2: ⚠️  C loop not compiled — using Python intervals")
    
    # Step 3: Run first miner cycle (attest + enroll with real HW data)
    log("Step 3: First attestation...")
    result = run_miner_cycle()
    if result.get("enrolled"):
        log(f"  ✅ Enrolled! Balance: {result.get('balance', 'unknown')} RTC")
    else:
        log(f"  ⚠️  Enrollment: {result.get('error', 'failed')}")
    
    # Step 4: Continuous mining loop
    log("Step 4: Continuous mining loop starting...")
    log(f"  Interval: {BASE_INTERVAL}s | Schedule: {CYCLES_PER_SCHEDULE} cycles")
    
    cycle = 0
    while running:
        cycle += 1
        log(f"─" * 50)
        log(f"Cycle #{cycle}")
        
        # Call the C loop for precise symplectic scheduling
        if os.path.exists(C_LOOP_BIN):
            c_result = subprocess.run(
                [C_LOOP_BIN, "--interval", str(BASE_INTERVAL), "--cycles", "1"],
                capture_output=True, text=True, timeout=BASE_INTERVAL + 60
            )
            # C loop handles one interval, returns after sleep
        else:
            # Python fallback: simple sleep
            time.sleep(BASE_INTERVAL)
        
        # Heartbeat
        heartbeat()
        
        # Re-attest and enroll
        result = run_miner_cycle()
        if result.get("enrolled"):
            log(f"  ✅ Re-enrolled. Balance: {result.get('balance', 'unknown')} RTC")
        else:
            log(f"  ⚠️  Re-enrollment: {result.get('error', 'retrying')}")
    
    log("Miner stopped.")

if __name__ == "__main__":
    main()
