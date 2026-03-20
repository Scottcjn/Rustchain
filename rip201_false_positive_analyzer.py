// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import hashlib

DB_PATH = 'blockchain.db'

@dataclass
class MinerScenario:
    name: str
    description: str
    miner_count: int
    shared_patterns: Dict[str, any]
    legitimate: bool
    expected_fleet_score: float

@dataclass
class FleetAnalysisResult:
    scenario_name: str
    fleet_score: float
    threshold_crossed: bool
    penalty_applied: bool
    false_positive: bool
    details: Dict[str, any]

class RIP201FalsePositiveAnalyzer:

    def __init__(self):
        self.current_threshold = 0.75
        self.penalty_threshold = 0.8
        self.scenarios = []
        self.results = []
        self.init_test_scenarios()

    def init_test_scenarios(self):
        """Initialize realistic mining scenarios for testing."""

        # Scenario 1: Small mining pool with shared infrastructure
        self.scenarios.append(MinerScenario(
            name="small_pool_shared_infra",
            description="10 miners in small pool sharing VPN/proxy for better connectivity",
            miner_count=10,
            shared_patterns={
                "ip_similarity": 0.8,
                "timing_correlation": 0.6,
                "ua_diversity": 0.4,
                "subnet_overlap": 0.9
            },
            legitimate=True,
            expected_fleet_score=0.72
        ))

        # Scenario 2: Corporate miners behind NAT
        self.scenarios.append(MinerScenario(
            name="corporate_nat_setup",
            description="15 miners in office environment behind corporate NAT/firewall",
            miner_count=15,
            shared_patterns={
                "ip_similarity": 0.95,
                "timing_correlation": 0.7,
                "ua_diversity": 0.3,
                "subnet_overlap": 1.0
            },
            legitimate=True,
            expected_fleet_score=0.81
        ))

        # Scenario 3: Cloud mining farm legitimate
        self.scenarios.append(MinerScenario(
            name="cloud_mining_legitimate",
            description="20 miners on AWS instances with similar configurations",
            miner_count=20,
            shared_patterns={
                "ip_similarity": 0.6,
                "timing_correlation": 0.5,
                "ua_diversity": 0.5,
                "subnet_overlap": 0.7
            },
            legitimate=True,
            expected_fleet_score=0.58
        ))

        # Scenario 4: Botnet attack simulation
        self.scenarios.append(MinerScenario(
            name="botnet_attack",
            description="25 compromised machines mining in coordination",
            miner_count=25,
            shared_patterns={
                "ip_similarity": 0.4,
                "timing_correlation": 0.9,
                "ua_diversity": 0.1,
                "subnet_overlap": 0.3
            },
            legitimate=False,
            expected_fleet_score=0.85
        ))

        # Scenario 5: Home miners on same ISP
        self.scenarios.append(MinerScenario(
            name="home_miners_same_isp",
            description="8 home miners in same city using same ISP",
            miner_count=8,
            shared_patterns={
                "ip_similarity": 0.7,
                "timing_correlation": 0.3,
                "ua_diversity": 0.8,
                "subnet_overlap": 0.8
            },
            legitimate=True,
            expected_fleet_score=0.45
        ))

    def simulate_mining_data(self, scenario: MinerScenario) -> List[Dict]:
        """Generate realistic mining data for a scenario."""
        miners = []
        base_ip = f"192.168.{random.randint(1, 254)}"

        for i in range(scenario.miner_count):
            # Generate miner identity
            miner_id = f"miner_{scenario.name}_{i:03d}"

            # IP assignment based on scenario
            if scenario.shared_patterns["ip_similarity"] > 0.9:
                ip = f"{base_ip}.{i + 10}"
            elif scenario.shared_patterns["ip_similarity"] > 0.7:
                subnet_var = random.randint(0, 2)
                ip = f"192.168.{random.randint(1, 254)}.{i + 10 + subnet_var}"
            else:
                ip = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{i + 10}"

            # User agent diversity
            if scenario.shared_patterns["ua_diversity"] < 0.3:
                ua = "RustChain-Miner/1.0"
            elif scenario.shared_patterns["ua_diversity"] < 0.6:
                ua = f"RustChain-Miner/1.{random.randint(0, 2)}"
            else:
                ua = f"RustChain-Miner/{random.randint(1, 3)}.{random.randint(0, 5)}"

            # Mining timing patterns
            base_time = datetime.now()
            if scenario.shared_patterns["timing_correlation"] > 0.8:
                last_block_time = base_time + timedelta(seconds=i * 2)
            elif scenario.shared_patterns["timing_correlation"] > 0.5:
                last_block_time = base_time + timedelta(seconds=random.randint(0, 300))
            else:
                last_block_time = base_time + timedelta(seconds=random.randint(0, 3600))

            miners.append({
                "miner_id": miner_id,
                "ip_address": ip,
                "user_agent": ua,
                "last_block_time": last_block_time,
                "hash_rate": random.randint(100, 1000),
                "blocks_mined": random.randint(1, 50)
            })

        return miners

    def calculate_fleet_score(self, miners: List[Dict]) -> Tuple[float, Dict]:
        """Calculate fleet detection score for a group of miners."""
        if len(miners) < 2:
            return 0.0, {"reason": "insufficient_miners"}

        # IP similarity analysis
        ip_groups = defaultdict(int)
        for miner in miners:
            subnet = ".".join(miner["ip_address"].split(".")[:3])
            ip_groups[subnet] += 1

        max_ip_group = max(ip_groups.values())
        ip_similarity = max_ip_group / len(miners)

        # User agent analysis
        ua_groups = defaultdict(int)
        for miner in miners:
            ua_groups[miner["user_agent"]] += 1

        ua_diversity = len(ua_groups) / len(miners)
        ua_concentration = max(ua_groups.values()) / len(miners)

        # Timing correlation analysis
        times = [miner["last_block_time"] for miner in miners]
        times.sort()

        time_diffs = []
        for i in range(1, len(times)):
            diff = (times[i] - times[i-1]).total_seconds()
            time_diffs.append(diff)

        avg_time_diff = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        timing_correlation = 1.0 - min(avg_time_diff / 3600, 1.0)

        # Hash rate pattern analysis
        hash_rates = [miner["hash_rate"] for miner in miners]
        hash_rate_variance = (max(hash_rates) - min(hash_rates)) / max(hash_rates) if hash_rates else 0
        hash_rate_similarity = 1.0 - hash_rate_variance

        # Composite fleet score calculation
        fleet_score = (
            ip_similarity * 0.3 +
            ua_concentration * 0.25 +
            timing_correlation * 0.25 +
            hash_rate_similarity * 0.2
        )

        details = {
            "ip_similarity": ip_similarity,
            "ua_diversity": ua_diversity,
            "ua_concentration": ua_concentration,
            "timing_correlation": timing_correlation,
            "hash_rate_similarity": hash_rate_similarity,
            "miner_count": len(miners),
            "composite_score": fleet_score
        }

        return fleet_score, details

    def analyze_scenario(self, scenario: MinerScenario) -> FleetAnalysisResult:
        """Analyze a single mining scenario for false positives."""
        miners = self.simulate_mining_data(scenario)
        fleet_score, details = self.calculate_fleet_score(miners)

        threshold_crossed = fleet_score >= self.current_threshold
        penalty_applied = fleet_score >= self.penalty_threshold
        false_positive = scenario.legitimate and penalty_applied

        return FleetAnalysisResult(
            scenario_name=scenario.name,
            fleet_score=fleet_score,
            threshold_crossed=threshold_crossed,
            penalty_applied=penalty_applied,
            false_positive=false_positive,
            details=details
        )

    def run_comprehensive_analysis(self) -> Dict:
        """Run analysis on all scenarios and generate report."""
        self.results = []
        false_positives = []
        legitimate_penalized = 0
        malicious_detected = 0

        print(f"Running RIP-201 False Positive Analysis...")
        print(f"Current threshold: {self.current_threshold}")
        print(f"Penalty threshold: {self.penalty_threshold}")
        print("-" * 60)

        for scenario in self.scenarios:
            result = self.analyze_scenario(scenario)
            self.results.append(result)

            print(f"Scenario: {scenario.name}")
            print(f"  Description: {scenario.description}")
            print(f"  Legitimate: {scenario.legitimate}")
            print(f"  Fleet Score: {result.fleet_score:.3f}")
            print(f"  Threshold Crossed: {result.threshold_crossed}")
            print(f"  Penalty Applied: {result.penalty_applied}")
            print(f"  False Positive: {result.false_positive}")

            if result.false_positive:
                false_positives.append(result)
                legitimate_penalized += 1
                print(f"  ⚠️  FALSE POSITIVE DETECTED")

            if not scenario.legitimate and result.penalty_applied:
                malicious_detected += 1
                print(f"  ✅ Malicious activity correctly detected")

            print()

        return {
            "total_scenarios": len(self.scenarios),
            "false_positives": len(false_positives),
            "legitimate_penalized": legitimate_penalized,
            "malicious_detected": malicious_detected,
            "false_positive_rate": len(false_positives) / len([s for s in self.scenarios if s.legitimate]),
            "detection_rate": malicious_detected / len([s for s in self.scenarios if not s.legitimate]),
            "threshold_recommendations": self.generate_threshold_recommendations(),
            "mitigation_strategies": self.generate_mitigation_strategies(false_positives)
        }

    def generate_threshold_recommendations(self) -> Dict:
        """Generate threshold adjustment recommendations."""
        legitimate_scores = [r.fleet_score for r in self.results
                           for s in self.scenarios
                           if s.name == r.scenario_name and s.legitimate]

        malicious_scores = [r.fleet_score for r in self.results
                          for s in self.scenarios
                          if s.name == r.scenario_name and not s.legitimate]

        if not legitimate_scores or not malicious_scores:
            return {"error": "insufficient_data"}

        max_legitimate = max(legitimate_scores)
        min_malicious = min(malicious_scores)

        optimal_threshold = (max_legitimate + min_malicious) / 2

        return {
            "current_threshold": self.current_threshold,
            "max_legitimate_score": max_legitimate,
            "min_malicious_score": min_malicious,
            "recommended_threshold": optimal_threshold,
            "improvement_needed": optimal_threshold != self.current_threshold
        }

    def generate_mitigation_strategies(self, false_positives: List[FleetAnalysisResult]) -> List[Dict]:
        """Generate mitigation strategies for false positives."""
        strategies = []

        if not false_positives:
            return [{"strategy": "no_false_positives", "description": "No mitigation needed"}]

        # Analyze common patterns in false positives
        ip_issues = sum(1 for fp in false_positives if fp.details["ip_similarity"] > 0.8)
        timing_issues = sum(1 for fp in false_positives if fp.details["timing_correlation"] > 0.7)
        ua_issues = sum(1 for fp in false_positives if fp.details["ua_concentration"] > 0.8)

        if ip_issues > 0:
            strategies.append({
                "strategy": "ip_similarity_adjustment",
                "description": "Reduce weight of IP similarity in fleet scoring for legitimate NAT/proxy scenarios",
                "affected_scenarios": ip_issues,
                "recommendation": "Lower IP similarity weight from 0.3 to 0.2 in scoring algorithm"
            })

        if timing_issues > 0:
            strategies.append({
                "strategy": "timing_correlation_refinement",
                "description": "Implement time window analysis to distinguish coordinated attacks from coincidental timing",
                "affected_scenarios": timing_issues,
                "recommendation": "Add randomization tolerance window of ±10 minutes for legitimate miners"
            })

        if ua_issues > 0:
            strategies.append({
                "strategy": "user_agent_whitelist",
                "description": "Maintain whitelist of known legitimate mining software versions",
                "affected_scenarios": ua_issues,
                "recommendation": "Reduce UA concentration penalty for whitelisted mining software"
            })

        # Always recommend multi-factor verification
        strategies.append({
            "strategy": "multi_factor_verification",
            "description": "Implement additional verification before applying penalties",
            "recommendation": "Require 2+ suspicious factors before penalty application"
        })

        return strategies

    def generate_detailed_report(self) -> str:
        """Generate detailed false positive analysis report."""
        analysis = self.run_comprehensive_analysis()

        report = []
        report.append("RIP-201 FALSE POSITIVE ANALYSIS REPORT")
        report.append("=" * 50)
        report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Scenarios Tested: {analysis['total_scenarios']}")
        report.append(f"False Positives Detected: {analysis['false_positives']}")
        report.append(f"False Positive Rate: {analysis['false_positive_rate']:.2%}")
        report.append(f"Detection Rate: {analysis['detection_rate']:.2%}")
        report.append("")

        report.append("THRESHOLD ANALYSIS")
        report.append("-" * 30)
        thresh_rec = analysis["threshold_recommendations"]
        if "error" not in thresh_rec:
            report.append(f"Current Threshold: {thresh_rec['current_threshold']}")
            report.append(f"Max Legitimate Score: {thresh_rec['max_legitimate_score']:.3f}")
            report.append(f"Min Malicious Score: {thresh_rec['min_malicious_score']:.3f}")
            report.append(f"Recommended Threshold: {thresh_rec['recommended_threshold']:.3f}")

            if thresh_rec['improvement_needed']:
                report.append("⚠️  THRESHOLD ADJUSTMENT RECOMMENDED")
            else:
                report.append("✅ Current threshold appears optimal")
        report.append("")

        report.append("MITIGATION STRATEGIES")
        report.append("-" * 30)
        for i, strategy in enumerate(analysis["mitigation_strategies"], 1):
            report.append(f"{i}. {strategy['strategy'].upper()}")
            report.append(f"   Description: {strategy['description']}")
            report.append(f"   Recommendation: {strategy['recommendation']}")
            report.append("")

        report.append("DETAILED SCENARIO RESULTS")
        report.append("-" * 30)
        for result in self.results:
            scenario = next(s for s in self.scenarios if s.name == result.scenario_name)
            report.append(f"Scenario: {scenario.name}")
            report.append(f"  Type: {'Legitimate' if scenario.legitimate else 'Malicious'}")
            report.append(f"  Fleet Score: {result.fleet_score:.3f}")
            report.append(f"  Status: {'FALSE POSITIVE' if result.false_positive else 'Correct'}")
            report.append(f"  Details: IP_sim={result.details['ip_similarity']:.2f}, "
                        f"UA_conc={result.details['ua_concentration']:.2f}, "
                        f"Time_corr={result.details['timing_correlation']:.2f}")
            report.append("")

        return "\n".join(report)

    def save_results_to_db(self):
        """Save analysis results to database for tracking."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS rip201_false_positive_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_date TEXT,
                    scenario_name TEXT,
                    legitimate INTEGER,
                    fleet_score REAL,
                    false_positive INTEGER,
                    details TEXT
                )
            ''')

            for result in self.results:
                scenario = next(s for s in self.scenarios if s.name == result.scenario_name)
                conn.execute('''
                    INSERT INTO rip201_false_positive_tests
                    (test_date, scenario_name, legitimate, fleet_score, false_positive, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().isoformat(),
                    result.scenario_name,
                    int(scenario.legitimate),
                    result.fleet_score,
                    int(result.false_positive),
                    json.dumps(result.details)
                ))

            conn.commit()

def main():
    """Run the false positive analysis."""
    analyzer = RIP201FalsePositiveAnalyzer()

    print("Starting RIP-201 False Positive Analysis...")
    report = analyzer.generate_detailed_report()

    # Save to file
    with open(f"rip201_false_positive_report_{int(time.time())}.txt", "w") as f:
        f.write(report)

    # Save to database
    analyzer.save_results_to_db()

    print("Analysis complete. Report saved.")
    print("\n" + "="*50)
    print(report)

if __name__ == "__main__":
    main()
