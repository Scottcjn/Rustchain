// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import random
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime, timedelta

@dataclass
class MinerProfile:
    node_id: str
    ip_address: str
    location: str
    hardware_type: str
    setup_type: str
    operator: str
    mining_power: float
    uptime_pattern: str
    connection_stability: float

@dataclass
class MiningScenario:
    name: str
    description: str
    miners: List[MinerProfile]
    expected_fleet_score: float
    legitimate: bool
    risk_factors: List[str]

class FleetScenarioGenerator:
    def __init__(self):
        self.ip_pools = {
            'university': ['10.0.{}.{}', '192.168.{}.{}'],
            'corporate': ['172.16.{}.{}', '10.{}.{}.{}'],
            'datacenter': ['203.0.{}.{}', '198.51.{}.{}'],
            'residential': ['73.{}.{}.{}', '96.{}.{}.{}', '24.{}.{}.{}'],
            'shared_hosting': ['45.{}.{}.{}', '104.{}.{}.{}']
        }

        self.hardware_profiles = {
            'high_end_gpu': {'power': 150.0, 'stability': 0.95},
            'mid_range_gpu': {'power': 80.0, 'stability': 0.88},
            'asic_miner': {'power': 300.0, 'stability': 0.92},
            'cpu_only': {'power': 5.0, 'stability': 0.75},
            'laptop': {'power': 12.0, 'stability': 0.60},
            'server_grade': {'power': 200.0, 'stability': 0.98}
        }

    def generate_ip_address(self, network_type: str) -> str:
        pool = random.choice(self.ip_pools[network_type])
        return pool.format(
            random.randint(1, 254),
            random.randint(1, 254),
            random.randint(1, 254),
            random.randint(1, 254)
        )

    def create_university_lab_scenario(self) -> MiningScenario:
        miners = []
        base_node_id = f"univ_{random.randint(1000, 9999)}"

        for i in range(random.randint(8, 24)):
            miners.append(MinerProfile(
                node_id=f"{base_node_id}_lab{i:02d}",
                ip_address=self.generate_ip_address('university'),
                location=f"Computer Lab {chr(65 + i//8)}",
                hardware_type=random.choice(['high_end_gpu', 'mid_range_gpu']),
                setup_type="university_research",
                operator="CS Department",
                mining_power=self.hardware_profiles[random.choice(['high_end_gpu', 'mid_range_gpu'])]['power'],
                uptime_pattern="academic_hours",
                connection_stability=0.85
            ))

        return MiningScenario(
            name="University Research Lab",
            description="Computer science department running distributed mining experiment across multiple lab machines",
            miners=miners,
            expected_fleet_score=0.75,
            legitimate=True,
            risk_factors=['similar_hardware', 'coordinated_timing', 'sequential_ips']
        )

    def create_corporate_mining_farm(self) -> MiningScenario:
        miners = []
        company_id = f"corp_{random.randint(100, 999)}"

        for rack in range(random.randint(3, 8)):
            for unit in range(random.randint(4, 12)):
                miners.append(MinerProfile(
                    node_id=f"{company_id}_r{rack}u{unit:02d}",
                    ip_address=self.generate_ip_address('corporate'),
                    location=f"Datacenter Rack {rack}",
                    hardware_type="asic_miner",
                    setup_type="corporate_farm",
                    operator="Mining Corp Ltd",
                    mining_power=self.hardware_profiles['asic_miner']['power'],
                    uptime_pattern="24x7",
                    connection_stability=0.96
                ))

        return MiningScenario(
            name="Corporate Mining Farm",
            description="Legitimate business operating professional mining facility with enterprise-grade equipment",
            miners=miners,
            expected_fleet_score=0.92,
            legitimate=True,
            risk_factors=['identical_hardware', 'same_operator', 'high_coordination', 'datacenter_ips']
        )

    def create_family_operation_scenario(self) -> MiningScenario:
        miners = []
        family_id = f"fam_{random.randint(1000, 9999)}"

        # Parents' gaming rigs
        for i in range(2):
            miners.append(MinerProfile(
                node_id=f"{family_id}_parent{i+1}",
                ip_address=self.generate_ip_address('residential'),
                location=f"Home Office {i+1}",
                hardware_type="high_end_gpu",
                setup_type="family_mining",
                operator="Family Mining",
                mining_power=self.hardware_profiles['high_end_gpu']['power'],
                uptime_pattern="evening_weekend",
                connection_stability=0.82
            ))

        # Kids' computers
        for i in range(random.randint(1, 3)):
            miners.append(MinerProfile(
                node_id=f"{family_id}_kid{i+1}",
                ip_address=self.generate_ip_address('residential'),
                location=f"Bedroom {i+1}",
                hardware_type=random.choice(['mid_range_gpu', 'laptop']),
                setup_type="family_mining",
                operator="Family Mining",
                mining_power=self.hardware_profiles[random.choice(['mid_range_gpu', 'laptop'])]['power'],
                uptime_pattern="after_school",
                connection_stability=0.70
            ))

        return MiningScenario(
            name="Family Mining Operation",
            description="Family running mining software on personal computers during off-hours",
            miners=miners,
            expected_fleet_score=0.45,
            legitimate=True,
            risk_factors=['same_household', 'coordinated_setup']
        )

    def create_shared_hosting_scenario(self) -> MiningScenario:
        miners = []
        provider_id = f"host_{random.randint(100, 999)}"

        # VPS customers mining independently
        for customer in range(random.randint(15, 35)):
            miners.append(MinerProfile(
                node_id=f"{provider_id}_vps{customer:03d}",
                ip_address=self.generate_ip_address('shared_hosting'),
                location=f"VPS Customer {customer}",
                hardware_type="server_grade",
                setup_type="vps_mining",
                operator=f"Customer_{customer}",
                mining_power=self.hardware_profiles['server_grade']['power'] * random.uniform(0.3, 0.8),
                uptime_pattern="variable",
                connection_stability=0.88
            ))

        return MiningScenario(
            name="Shared Hosting Provider",
            description="Multiple independent customers mining on VPS instances from same hosting provider",
            miners=miners,
            expected_fleet_score=0.68,
            legitimate=True,
            risk_factors=['same_datacenter', 'similar_infrastructure', 'ip_proximity']
        )

    def create_gaming_cafe_scenario(self) -> MiningScenario:
        miners = []
        cafe_id = f"cafe_{random.randint(100, 999)}"

        for station in range(random.randint(12, 30)):
            miners.append(MinerProfile(
                node_id=f"{cafe_id}_pc{station:02d}",
                ip_address=self.generate_ip_address('corporate'),
                location=f"Gaming Station {station}",
                hardware_type="high_end_gpu",
                setup_type="gaming_cafe",
                operator="Cafe Owner",
                mining_power=self.hardware_profiles['high_end_gpu']['power'],
                uptime_pattern="business_hours_idle",
                connection_stability=0.85
            ))

        return MiningScenario(
            name="Gaming Cafe Mining",
            description="Internet cafe mining during idle hours when gaming PCs are not in use",
            miners=miners,
            expected_fleet_score=0.82,
            legitimate=True,
            risk_factors=['identical_hardware', 'same_location', 'coordinated_operation']
        )

    def generate_false_positive_report(self) -> Dict[str, Any]:
        scenarios = [
            self.create_university_lab_scenario(),
            self.create_corporate_mining_farm(),
            self.create_family_operation_scenario(),
            self.create_shared_hosting_scenario(),
            self.create_gaming_cafe_scenario()
        ]

        report = {
            'generated_at': datetime.now().isoformat(),
            'total_scenarios': len(scenarios),
            'scenarios': [],
            'false_positive_analysis': {
                'threshold_crossers': [],
                'risk_factor_frequency': {},
                'recommendations': []
            }
        }

        risk_factor_counts = {}

        for scenario in scenarios:
            scenario_data = asdict(scenario)
            scenario_data['miners'] = [asdict(miner) for miner in scenario.miners]
            report['scenarios'].append(scenario_data)

            # Analyze risk factors
            for risk_factor in scenario.risk_factors:
                risk_factor_counts[risk_factor] = risk_factor_counts.get(risk_factor, 0) + 1

            # Check if legitimate scenario crosses penalty threshold
            if scenario.legitimate and scenario.expected_fleet_score > 0.8:
                report['false_positive_analysis']['threshold_crossers'].append({
                    'scenario_name': scenario.name,
                    'fleet_score': scenario.expected_fleet_score,
                    'miner_count': len(scenario.miners),
                    'primary_risk_factors': scenario.risk_factors
                })

        report['false_positive_analysis']['risk_factor_frequency'] = risk_factor_counts

        # Generate recommendations based on analysis
        recommendations = []
        if len(report['false_positive_analysis']['threshold_crossers']) > 0:
            recommendations.append("Consider implementing graduated penalties instead of hard thresholds")
            recommendations.append("Add whitelist mechanism for verified legitimate operations")

        if 'same_datacenter' in risk_factor_counts and risk_factor_counts['same_datacenter'] > 2:
            recommendations.append("Develop datacenter IP range detection to reduce shared hosting false positives")

        recommendations.append("Implement time-based pattern analysis to distinguish coordinated attacks from legitimate shared operations")

        report['false_positive_analysis']['recommendations'] = recommendations

        return report

    def export_scenario_json(self, filename: str = None) -> str:
        if filename is None:
            filename = f"fleet_false_positive_report_{int(time.time())}.json"

        report = self.generate_false_positive_report()

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        return filename

if __name__ == "__main__":
    generator = FleetScenarioGenerator()

    print("Generating Fleet Detection False Positive Scenarios...")
    report_file = generator.export_scenario_json()
    print(f"Report saved to: {report_file}")

    # Quick summary
    report = generator.generate_false_positive_report()
    print(f"\nGenerated {report['total_scenarios']} legitimate mining scenarios")
    print(f"False positive candidates: {len(report['false_positive_analysis']['threshold_crossers'])}")

    for scenario in report['false_positive_analysis']['threshold_crossers']:
        print(f"  - {scenario['scenario_name']}: {scenario['fleet_score']:.2f} score with {scenario['miner_count']} miners")
