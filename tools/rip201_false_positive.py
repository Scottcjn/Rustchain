#!/usr/bin/env python3
"""
RIP-201 False Positive Testing
Bounty #493 - 100 RTC
"""

import json
import random
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple


@dataclass
class MinerProfile:
    miner_id: str
    ip_address: str
    subnet: str
    hardware_fingerprint: str
    device_family: str
    last_attest: int
    user_type: str


@dataclass
class FleetScore:
    ip_clustering: float
    fingerprint_similarity: float
    timing_correlation: float
    total_score: float


class FleetDetectionSimulator:
    def __init__(self):
        self.ip_weight = 0.4
        self.fingerprint_weight = 0.4
        self.timing_weight = 0.2
    
    def calculate_ip_clustering(self, miners: List[MinerProfile]) -> float:
        if not miners:
            return 0.0
        subnets = {}
        for m in miners:
            subnets[m.subnet] = subnets.get(m.subnet, 0) + 1
        max_in_subnet = max(subnets.values())
        return min(max_in_subnet / len(miners), 1.0)
    
    def calculate_fingerprint_similarity(self, miners: List[MinerProfile]) -> float:
        if not miners or len(miners) < 2:
            return 0.0
        fingerprints = {}
        for m in miners:
            fingerprints[m.hardware_fingerprint] = fingerprints.get(m.hardware_fingerprint, 0) + 1
        max_identical = max(fingerprints.values())
        return min(max_identical / len(miners), 1.0)
    
    def calculate_timing_correlation(self, miners: List[MinerProfile]) -> float:
        if not miners or len(miners) < 2:
            return 0.0
        time_windows = {}
        for m in miners:
            window = m.last_attest // 300
            time_windows[window] = time_windows.get(window, 0) + 1
        max_in_window = max(time_windows.values())
        return min(max_in_window / len(miners), 1.0)
    
    def calculate_fleet_score(self, miners: List[MinerProfile]) -> FleetScore:
        ip_score = self.calculate_ip_clustering(miners)
        fp_score = self.calculate_fingerprint_similarity(miners)
        timing_score = self.calculate_timing_correlation(miners)
        total = ip_score * self.ip_weight + fp_score * self.fingerprint_weight + timing_score * self.timing_weight
        return FleetScore(ip_clustering=ip_score, fingerprint_similarity=fp_score, timing_correlation=timing_score, total_score=total)


class FalsePositiveScenarios:
    @staticmethod
    def university_computer_lab() -> Tuple[str, List[MinerProfile]]:
        miners = []
        base_time = 1700000000
        for i in range(20):
            miners.append(MinerProfile(
                miner_id=f"student_{i+1}",
                ip_address=f"203.0.113.{10+i}",
                subnet="203.0.113.0/24",
                hardware_fingerprint="Dell_OptiPlex_7090",
                device_family="x86",
                last_attest=base_time + random.randint(-300, 300),
                user_type="student"
            ))
        return "University Computer Lab", miners
    
    @staticmethod
    def internet_cafe() -> Tuple[str, List[MinerProfile]]:
        miners = []
        base_time = 1700000000
        for i in range(15):
            miners.append(MinerProfile(
                miner_id=f"cafe_customer_{i+1}",
                ip_address="198.51.100.1",
                subnet="198.51.100.0/24",
                hardware_fingerprint=f"Device_{i+1}",
                device_family=random.choice(["x86", "arm"]),
                last_attest=base_time + random.randint(-600, 600),
                user_type="cafe_customer"
            ))
        return "Internet Cafe", miners


def main():
    simulator = FleetDetectionSimulator()
    scenarios = [
        FalsePositiveScenarios.university_computer_lab(),
        FalsePositiveScenarios.internet_cafe()
    ]
    
    results = []
    for name, miners in scenarios:
        score = simulator.calculate_fleet_score(miners)
        results.append({
            "scenario": name,
            "miner_count": len(miners),
            "fleet_score": round(score.total_score, 3),
            "ip_clustering": round(score.ip_clustering, 3),
            "fingerprint_similarity": round(score.fingerprint_similarity, 3),
            "timing_correlation": round(score.timing_correlation, 3),
            "false_positive": score.total_score > 0.3
        })
    
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
