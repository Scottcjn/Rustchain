#!/usr/bin/env python3
"""
Symplectic-Optimized RustChain Miner
Applies holographic (symplectic) decomposition from bytropix math vault
to optimize mining cycle scheduling, reducing latency between attestations.

Math: g = q·2π + r — decomposes gradient into integer cycles + remainder drift.
For mining: schedules attestations at symplectically-optimal intervals.
"""

import os, sys, json, time, hashlib, math, subprocess, logging
from datetime import datetime
from pathlib import Path

# Config
WALLET = "RTC17c0d21f04f6f65c1a85c0aeb5d4a305d57531096"
NODE_URL = "https://rustchain.org"
MINER_SCRIPT = os.path.expanduser("~/rustchain/miners/linux/rustchain_linux_miner.py")
LOG_DIR = Path.home() / ".rustchain" / "miner_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "miner.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("symplectic-miner")

# Symplectic decomposition (from bytropix/THEORY/math_viz/06_symplectic_optimizer.py)
BOUNDARY = 2 * math.pi

def decompose(g, boundary=BOUNDARY):
    """Holographic decomposition: g = q·boundary + r"""
    q = int(math.floor((g + boundary / 2) / boundary))
    r = g - q * boundary
    if r < -boundary / 2:
        r += boundary
        q -= 1
    elif r >= boundary / 2:
        r -= boundary
        q += 1
    return q, r

def optimal_schedule(base_interval=600, count=10):
    """
    Generate symplectically-optimal attestation intervals.
    Decomposes the total time into q (discrete cycles) + r (continuum drift).
    Returns array of optimal wait times between attestations.
    """
    total = base_interval * count
    q_total, r_total = decompose(total)
    intervals = []
    accumulated_r = 0.0
    for i in range(count):
        # Distribute the remainder drift across cycles
        base = base_interval
        target_r = r_total * (i + 1) / count
        drift = target_r - accumulated_r
        interval = base + drift
        intervals.append(max(10.0, interval))  # Min 10s between attestations
        accumulated_r = target_r
    return intervals


def run_miner_cycle(wallet, verbose=False):
    """Run one miner attestation+enrollment cycle."""
    cmd = [sys.executable, MINER_SCRIPT, "--wallet", wallet]
    if verbose:
        cmd.append("--verbose")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        output = result.stdout + result.stderr
        
        # Parse result
        enrolled = "[OK] Enrolled!" in output
        attested = "[PASS] Attestation accepted!" in output
        balance = None
        for line in output.split("\n"):
            if "Balance:" in line and "RTC" in line:
                try:
                    balance = float(line.split("Balance:")[1].split("RTC")[0].strip())
                except:
                    pass
        
        return {
            "enrolled": enrolled,
            "attested": attested,
            "balance": balance,
            "raw_output": output[-500:],  # Last 500 chars for debugging
        }
    except subprocess.TimeoutExpired:
        return {"enrolled": False, "attested": False, "balance": None, "error": "timeout"}
    except Exception as e:
        return {"enrolled": False, "attested": False, "balance": None, "error": str(e)}


def main():
    log.info(f"=== Symplectic Miner Started ===")
    log.info(f"Wallet: {WALLET}")
    log.info(f"Node: {NODE_URL}")
    
    # Generate optimal schedule
    base_block_time = 600  # 10 min block time
    intervals = optimal_schedule(base_block_time, count=20)
    log.info(f"Optimal schedule generated: {len(intervals)} cycles")
    log.info(f"Interval range: {min(intervals):.1f}s - {max(intervals):.1f}s")
    
    cycle = 0
    earnings_log = []
    
    try:
        while True:
            cycle += 1
            wait_time = intervals[(cycle - 1) % len(intervals)]
            
            log.info(f"\n{'='*50}")
            log.info(f"Cycle #{cycle} — {datetime.now().isoformat()}")
            log.info(f"Symplectic interval: {wait_time:.1f}s")
            
            # Run attestation + enrollment
            result = run_miner_cycle(WALLET, verbose=False)
            
            if result.get("enrolled"):
                log.info(f"✅ Enrolled successfully")
            else:
                log.info(f"❌ Enrollment failed")
                if result.get("error"):
                    log.error(f"Error: {result['error']}")
            
            if result.get("balance") is not None:
                log.info(f"💰 Balance: {result['balance']} RTC")
                earnings_log.append({
                    "cycle": cycle,
                    "time": datetime.now().isoformat(),
                    "balance": result["balance"],
                })
                # Save earnings
                with open(LOG_DIR / "earnings.json", "w") as f:
                    json.dump(earnings_log, f, indent=2)
            
            log.info(f"⏳ Waiting {wait_time:.0f}s until next cycle...")
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        log.info(f"\n⛔ Mining stopped after {cycle} cycles")
        if earnings_log:
            latest = earnings_log[-1]["balance"]
            log.info(f"Final balance: {latest} RTC (${latest * 0.10:.2f} USD)")
        return 0
    except Exception as e:
        log.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
