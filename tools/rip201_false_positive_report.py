#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-201 False Positive Analysis — Bounty #493

Simulates realistic scenarios where LEGITIMATE independent miners
get incorrectly flagged by fleet detection, and proposes mitigations.

Scenarios:
1. University Campus — 6 students on same /24 campus network
2. Cloud Hosting — 5 independent miners on same AWS /24
3. Coworking Space — 4 freelancers on same office WiFi
4. ISP Carrier-Grade NAT — 8 homes behind same CGNAT /24
5. Same Hardware Model — 5 students with identical MacBook M2s
6. Timezone Clustering — 10 miners in same timezone attesting around same hour
"""

import importlib.util
import json
import random
import sqlite3
from pathlib import Path


def load_fleet_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "rips" / "python" / "rustchain" / "fleet_immune_system.py"
    )
    spec = importlib.util.spec_from_file_location("fleet_fp_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_fingerprint(cv=0.052, l1=4.1, l2=10.2, entropy=0.61, simd="default"):
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"],
                         "dmesg_scanned": True},
            },
            "clock_drift": {"passed": True, "data": {"cv": round(cv, 4), "samples": 64}},
            "cache_timing": {"passed": True, "data": {"l1_hit_ns": l1, "l2_hit_ns": l2}},
            "thermal_drift": {"passed": True, "data": {"entropy": entropy}},
            "simd_identity": {"passed": True, "data": {"profile": simd}},
        },
        "all_passed": True,
    }


def run_scenario(fleet_mod, name, description, miners_config):
    """Run a scenario and return results."""
    db = sqlite3.connect(":memory:")
    fleet_mod.ensure_schema(db)

    epoch = 1000
    for cfg in miners_config:
        fleet_mod.record_fleet_signals_from_request(
            db, miner=cfg["id"], epoch=epoch,
            ip_address=cfg["ip"],
            attest_ts=cfg["ts"],
            fingerprint=cfg["fp"],
        )

    scores = fleet_mod.compute_fleet_scores(db, epoch)
    penalized = {m: s for m, s in scores.items() if s >= 0.3}
    clean = {m: s for m, s in scores.items() if s < 0.3}

    return {
        "scenario": name,
        "description": description,
        "num_miners": len(miners_config),
        "scores": {m: round(s, 4) for m, s in scores.items()},
        "penalized_count": len(penalized),
        "clean_count": len(clean),
        "max_score": round(max(scores.values()), 4) if scores else 0,
        "avg_score": round(sum(scores.values()) / len(scores), 4) if scores else 0,
        "is_false_positive": len(penalized) > 0,
        "multipliers": {
            m: round(fleet_mod.apply_fleet_decay(2.5, s), 4)
            for m, s in scores.items()
        },
    }


def scenario_university_campus(fleet_mod):
    """6 students mining from same university campus /24 network."""
    random.seed(101)
    miners = []
    for i in range(6):
        miners.append({
            "id": f"student-{i}",
            "ip": f"192.168.1.{10 + i}",  # Same /24 campus subnet
            "ts": 50000 + random.randint(0, 3600),  # Within same hour
            "fp": make_fingerprint(
                cv=round(random.uniform(0.03, 0.08), 4),
                l1=round(random.uniform(3.5, 5.0), 1),
                l2=round(random.uniform(9.0, 12.0), 1),
                entropy=round(random.uniform(0.4, 0.8), 2),
                simd=random.choice(["x86-avx2", "x86-sse4", "arm-neon", "x86-avx512"]),
            ),
        })
    return run_scenario(
        fleet_mod, "university_campus",
        "6 independent students mining from same campus /24 network. "
        "Different personal laptops (varied hardware), different dorm rooms, "
        "but ISP routes all through same /24 subnet. Attestation times "
        "naturally cluster because students mine during evening hours.",
        miners,
    )


def scenario_cloud_hosting(fleet_mod):
    """5 independent miners on same AWS region /24."""
    random.seed(102)
    miners = []
    for i in range(5):
        miners.append({
            "id": f"aws-miner-{i}",
            "ip": f"172.31.16.{100 + i}",  # Same AWS /24
            "ts": 80000 + i * 120,  # Fairly spread out
            "fp": make_fingerprint(
                cv=round(0.045 + random.uniform(-0.005, 0.005), 4),
                l1=round(3.8 + random.uniform(-0.2, 0.2), 1),
                l2=round(10.0 + random.uniform(-0.5, 0.5), 1),
                entropy=round(0.55 + random.uniform(-0.1, 0.1), 2),
                simd="x86-avx512",  # AWS instances often have same SIMD
            ),
        })
    return run_scenario(
        fleet_mod, "cloud_hosting",
        "5 independent miners each running on their own AWS EC2 instance. "
        "Same region (us-east-1) means same /24 subnet allocation. "
        "Similar instance types (c5.xlarge) produce similar fingerprints "
        "(same SIMD profile, similar cache timing). Miners don't know each other.",
        miners,
    )


def scenario_coworking_space(fleet_mod):
    """4 freelancers mining from same coworking space WiFi."""
    random.seed(103)
    miners = []
    for i in range(4):
        miners.append({
            "id": f"cowork-{i}",
            "ip": f"10.0.1.{50 + i}",  # Same office /24
            "ts": 40000 + random.randint(0, 1800),  # Within 30 min window
            "fp": make_fingerprint(
                cv=round(random.uniform(0.04, 0.07), 4),
                l1=round(random.uniform(3.5, 5.5), 1),
                l2=round(random.uniform(8.5, 13.0), 1),
                entropy=round(random.uniform(0.45, 0.75), 2),
                simd=random.choice(["arm-neon", "x86-avx2"]),
            ),
        })
    return run_scenario(
        fleet_mod, "coworking_space",
        "4 independent freelancers mining from same coworking space. "
        "Shared WiFi = same /24 IP. Different personal machines but "
        "attestation times cluster during work hours (9-5).",
        miners,
    )


def scenario_cgnat(fleet_mod):
    """8 households behind ISP carrier-grade NAT."""
    random.seed(104)
    miners = []
    for i in range(8):
        miners.append({
            "id": f"home-{i}",
            "ip": f"100.64.0.{i + 1}",  # CGNAT shared /24
            "ts": 70000 + random.randint(0, 7200),  # 2-hour window (evening)
            "fp": make_fingerprint(
                cv=round(random.uniform(0.02, 0.09), 4),
                l1=round(random.uniform(3.0, 6.0), 1),
                l2=round(random.uniform(8.0, 14.0), 1),
                entropy=round(random.uniform(0.3, 0.9), 2),
                simd=random.choice(["x86-avx2", "x86-sse4", "arm-neon", "x86-avx512", "arm-sve"]),
            ),
        })
    return run_scenario(
        fleet_mod, "isp_cgnat",
        "8 independent households behind ISP carrier-grade NAT. "
        "All traffic appears from same /24 despite being different homes "
        "with completely different hardware. Common in developing countries "
        "and mobile ISPs. Mining during evening hours creates timing cluster.",
        miners,
    )


def scenario_same_hardware(fleet_mod):
    """5 students with identical MacBook M2 laptops."""
    random.seed(105)
    miners = []
    for i in range(5):
        miners.append({
            "id": f"macbook-{i}",
            "ip": f"198.{51 + i}.0.10",  # Different /24 subnets (different ISPs)
            "ts": 60000 + random.randint(0, 14400),  # Well spread (4 hours)
            "fp": make_fingerprint(
                cv=0.052,   # Identical — same CPU
                l1=4.1,     # Identical — same cache hierarchy
                l2=10.2,    # Identical — same L2
                entropy=0.61,  # Very similar thermal characteristics
                simd="arm-neon",  # Identical — all M2
            ),
        })
    return run_scenario(
        fleet_mod, "same_hardware_model",
        "5 students from different cities each bought same MacBook M2 "
        "for university. Different ISPs (different /24), well-spread timing, "
        "but IDENTICAL hardware fingerprints because same CPU, cache, SIMD. "
        "They don't know each other exists.",
        miners,
    )


def scenario_timezone_cluster(fleet_mod):
    """10 miners in same timezone attesting around same hour."""
    random.seed(106)
    miners = []
    for i in range(10):
        miners.append({
            "id": f"tz-miner-{i}",
            "ip": f"203.{i + 10}.{random.randint(1, 254)}.{random.randint(1, 254)}",
            "ts": 90000 + random.randint(0, 25),  # Within 25-second window!
            "fp": make_fingerprint(
                cv=round(random.uniform(0.02, 0.09), 4),
                l1=round(random.uniform(3.0, 6.0), 1),
                l2=round(random.uniform(8.0, 14.0), 1),
                entropy=round(random.uniform(0.3, 0.9), 2),
                simd=random.choice(["x86-avx2", "x86-sse4", "arm-neon"]),
            ),
        })
    return run_scenario(
        fleet_mod, "timezone_clustering",
        "10 independent miners across a country (different IPs, different hardware) "
        "who all run cron jobs at the same local time (e.g., 8pm daily). "
        "Attestation timestamps cluster within the 30-second detection window "
        "purely by coincidence of cron scheduling.",
        miners,
    )


def main():
    fleet_mod = load_fleet_module()

    scenarios = [
        scenario_university_campus(fleet_mod),
        scenario_cloud_hosting(fleet_mod),
        scenario_coworking_space(fleet_mod),
        scenario_cgnat(fleet_mod),
        scenario_same_hardware(fleet_mod),
        scenario_timezone_cluster(fleet_mod),
    ]

    false_positives = [s for s in scenarios if s["is_false_positive"]]

    report = {
        "tool": "rip201_false_positive_report",
        "bounty": "#493 — RIP-201 False Positive Testing (100 RTC)",
        "total_scenarios": len(scenarios),
        "false_positive_scenarios": len(false_positives),
        "scenarios": scenarios,
        "summary": {
            name: {
                "false_positive": s["is_false_positive"],
                "max_score": s["max_score"],
                "penalized": s["penalized_count"],
                "total": s["num_miners"],
            }
            for s in scenarios
            for name in [s["scenario"]]
        },
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
