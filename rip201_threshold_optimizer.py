// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
import json

DB_PATH = 'rustchain.db'

class ThresholdOptimizer:
    def __init__(self):
        self.fleet_scores = []
        self.legitimate_scenarios = []
        self.malicious_scenarios = []
        self.current_threshold = 0.75

    def analyze_fleet_distributions(self):
        """Analyze current fleet score distributions from database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get fleet scores from recent mining activity
            cursor.execute("""
                SELECT miner_id, fleet_score, timestamp, block_height
                FROM mining_stats
                WHERE timestamp > datetime('now', '-7 days')
                AND fleet_score IS NOT NULL
                ORDER BY timestamp DESC
            """)

            raw_data = cursor.fetchall()

        fleet_data = {}
        for miner_id, score, timestamp, height in raw_data:
            if miner_id not in fleet_data:
                fleet_data[miner_id] = []
            fleet_data[miner_id].append({
                'score': float(score),
                'timestamp': timestamp,
                'height': height
            })

        return self._calculate_distribution_stats(fleet_data)

    def _calculate_distribution_stats(self, fleet_data):
        """Calculate statistical measures for fleet score distribution"""
        all_scores = []
        miner_stats = {}

        for miner_id, scores_data in fleet_data.items():
            scores = [d['score'] for d in scores_data]
            all_scores.extend(scores)

            miner_stats[miner_id] = {
                'mean': statistics.mean(scores),
                'median': statistics.median(scores),
                'std_dev': statistics.stdev(scores) if len(scores) > 1 else 0,
                'max': max(scores),
                'min': min(scores),
                'count': len(scores)
            }

        return {
            'global_stats': {
                'mean': statistics.mean(all_scores),
                'median': statistics.median(all_scores),
                'std_dev': statistics.stdev(all_scores) if len(all_scores) > 1 else 0,
                'percentiles': {
                    '25': self._percentile(all_scores, 25),
                    '75': self._percentile(all_scores, 75),
                    '90': self._percentile(all_scores, 90),
                    '95': self._percentile(all_scores, 95),
                    '99': self._percentile(all_scores, 99)
                }
            },
            'miner_stats': miner_stats,
            'total_scores': len(all_scores)
        }

    def _percentile(self, data, p):
        """Calculate percentile of dataset"""
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_data[int(k)]
        return sorted_data[int(f)] * (c - k) + sorted_data[int(c)] * (k - f)

    def define_legitimate_scenarios(self):
        """Define realistic legitimate mining scenarios that might trigger false positives"""
        scenarios = [
            {
                'name': 'University Mining Lab',
                'description': 'Computer science department with 20-30 identical machines on same subnet',
                'characteristics': {
                    'ip_similarity': 0.85,  # Same /24 subnet
                    'hardware_similarity': 0.95,  # Identical lab machines
                    'timing_pattern': 0.70,  # Class schedule coordination
                    'location_clustering': 0.90  # Same building
                },
                'expected_fleet_score': 0.85
            },
            {
                'name': 'Small Mining Farm',
                'description': 'Legitimate operation with 5-10 rigs in garage/basement',
                'characteristics': {
                    'ip_similarity': 0.95,  # Single residential IP
                    'hardware_similarity': 0.60,  # Mix of older hardware
                    'timing_pattern': 0.80,  # Power management coordination
                    'location_clustering': 0.98  # Same physical location
                },
                'expected_fleet_score': 0.83
            },
            {
                'name': 'Internet Cafe Mining',
                'description': 'Internet cafe allowing customers to mine during off-peak',
                'characteristics': {
                    'ip_similarity': 0.90,  # Single business IP/NAT
                    'hardware_similarity': 0.75,  # Similar gaming PCs
                    'timing_pattern': 0.65,  # Different user schedules
                    'location_clustering': 0.95  # Same business address
                },
                'expected_fleet_score': 0.81
            },
            {
                'name': 'Corporate Employee Mining',
                'description': 'Office workers mining on lunch breaks from company PCs',
                'characteristics': {
                    'ip_similarity': 0.88,  # Corporate network
                    'hardware_similarity': 0.80,  # Standard office PCs
                    'timing_pattern': 0.75,  # Lunch hour coordination
                    'location_clustering': 0.85  # Office building
                },
                'expected_fleet_score': 0.82
            }
        ]

        self.legitimate_scenarios = scenarios
        return scenarios

    def simulate_scenario_scores(self, scenario):
        """Calculate fleet score for a given scenario"""
        chars = scenario['characteristics']

        # Weight factors based on RIP-201 model
        weights = {
            'ip_similarity': 0.25,
            'hardware_similarity': 0.20,
            'timing_pattern': 0.25,
            'location_clustering': 0.30
        }

        fleet_score = sum(chars[key] * weights[key] for key in weights)

        # Add some realistic variance
        import random
        variance = random.uniform(-0.05, 0.05)
        fleet_score = max(0, min(1, fleet_score + variance))

        return fleet_score

    def evaluate_false_positive_risk(self, distributions):
        """Evaluate risk of false positives with current threshold"""
        results = {
            'current_threshold': self.current_threshold,
            'false_positive_scenarios': [],
            'legitimate_above_threshold': 0,
            'total_legitimate': len(self.legitimate_scenarios)
        }

        for scenario in self.legitimate_scenarios:
            simulated_score = self.simulate_scenario_scores(scenario)

            if simulated_score >= self.current_threshold:
                results['false_positive_scenarios'].append({
                    'scenario': scenario['name'],
                    'description': scenario['description'],
                    'fleet_score': simulated_score,
                    'threshold_exceeded': simulated_score - self.current_threshold
                })
                results['legitimate_above_threshold'] += 1

        results['false_positive_rate'] = results['legitimate_above_threshold'] / results['total_legitimate']

        return results

    def propose_threshold_adjustments(self, distributions, false_positive_analysis):
        """Propose new thresholds to reduce false positives"""
        proposals = []

        # Current stats
        global_stats = distributions['global_stats']
        current_fp_rate = false_positive_analysis['false_positive_rate']

        # Proposal 1: Statistical approach - use 95th percentile + buffer
        stat_threshold = global_stats['percentiles']['95'] + 0.02
        proposals.append({
            'method': 'statistical_95th',
            'threshold': round(stat_threshold, 3),
            'rationale': 'Set threshold at 95th percentile + 2% buffer to catch outliers while allowing normal variance'
        })

        # Proposal 2: Adaptive threshold based on scenario analysis
        max_legitimate_score = max(self.simulate_scenario_scores(s) for s in self.legitimate_scenarios)
        adaptive_threshold = max_legitimate_score + 0.03
        proposals.append({
            'method': 'adaptive_scenario',
            'threshold': round(adaptive_threshold, 3),
            'rationale': f'Threshold above highest legitimate scenario ({max_legitimate_score:.3f}) with 3% safety margin'
        })

        # Proposal 3: Two-tier system
        proposals.append({
            'method': 'two_tier_system',
            'warning_threshold': round(global_stats['percentiles']['90'], 3),
            'penalty_threshold': round(global_stats['percentiles']['99'], 3),
            'rationale': 'Warning at 90th percentile, penalties at 99th percentile for graduated response'
        })

        return proposals

    def validate_threshold_changes(self, new_threshold, distributions):
        """Validate proposed threshold changes"""
        validation = {
            'proposed_threshold': new_threshold,
            'current_threshold': self.current_threshold,
            'impact_analysis': {}
        }

        # Simulate impact on legitimate scenarios
        legitimate_affected = 0
        for scenario in self.legitimate_scenarios:
            score = self.simulate_scenario_scores(scenario)
            if score >= new_threshold:
                legitimate_affected += 1

        validation['impact_analysis']['legitimate_false_positives'] = legitimate_affected
        validation['impact_analysis']['false_positive_reduction'] = (
            self.evaluate_false_positive_risk(distributions)['legitimate_above_threshold'] - legitimate_affected
        )

        # Estimate coverage of actual fleet behavior
        global_stats = distributions['global_stats']
        estimated_coverage = len([s for s in range(int(global_stats['percentiles']['99'] * 1000))
                                if s/1000 >= new_threshold]) / 10

        validation['impact_analysis']['estimated_detection_coverage'] = f"{estimated_coverage}%"

        return validation

    def generate_optimization_report(self):
        """Generate comprehensive threshold optimization report"""
        print("=== RIP-201 Threshold Optimization Report ===")
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Analyze current distributions
        distributions = self.analyze_fleet_distributions()
        print("Current Fleet Score Distribution:")
        stats = distributions['global_stats']
        print(f"  Mean: {stats['mean']:.3f}")
        print(f"  Median: {stats['median']:.3f}")
        print(f"  95th Percentile: {stats['percentiles']['95']:.3f}")
        print(f"  99th Percentile: {stats['percentiles']['99']:.3f}")
        print()

        # Define and analyze legitimate scenarios
        self.define_legitimate_scenarios()
        print("Legitimate Mining Scenarios:")
        for scenario in self.legitimate_scenarios:
            score = self.simulate_scenario_scores(scenario)
            print(f"  {scenario['name']}: {score:.3f}")
            print(f"    {scenario['description']}")
        print()

        # False positive analysis
        fp_analysis = self.evaluate_false_positive_risk(distributions)
        print("False Positive Analysis:")
        print(f"  Current Threshold: {fp_analysis['current_threshold']}")
        print(f"  Legitimate Scenarios Above Threshold: {fp_analysis['legitimate_above_threshold']}/{fp_analysis['total_legitimate']}")
        print(f"  False Positive Rate: {fp_analysis['false_positive_rate']:.1%}")
        print()

        if fp_analysis['false_positive_scenarios']:
            print("  Scenarios Triggering False Positives:")
            for fp in fp_analysis['false_positive_scenarios']:
                print(f"    {fp['scenario']}: {fp['fleet_score']:.3f} (exceeded by {fp['threshold_exceeded']:.3f})")
        print()

        # Threshold proposals
        proposals = self.propose_threshold_adjustments(distributions, fp_analysis)
        print("Threshold Adjustment Proposals:")
        for i, proposal in enumerate(proposals, 1):
            print(f"  Proposal {i}: {proposal['method']}")
            if 'threshold' in proposal:
                print(f"    New Threshold: {proposal['threshold']}")
                validation = self.validate_threshold_changes(proposal['threshold'], distributions)
                print(f"    Impact: {validation['impact_analysis']['false_positive_reduction']} fewer false positives")
            else:
                print(f"    Warning Threshold: {proposal['warning_threshold']}")
                print(f"    Penalty Threshold: {proposal['penalty_threshold']}")
            print(f"    Rationale: {proposal['rationale']}")
        print()

        return {
            'distributions': distributions,
            'false_positive_analysis': fp_analysis,
            'proposals': proposals
        }

def main():
    """Run threshold optimization analysis"""
    optimizer = ThresholdOptimizer()
    report = optimizer.generate_optimization_report()

    # Save results to database
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Create optimization results table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threshold_optimization (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_date TEXT,
                current_threshold REAL,
                false_positive_rate REAL,
                proposals TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO threshold_optimization
            (analysis_date, current_threshold, false_positive_rate, proposals)
            VALUES (?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            optimizer.current_threshold,
            report['false_positive_analysis']['false_positive_rate'],
            json.dumps(report['proposals'])
        ))

if __name__ == '__main__':
    main()
