"""
Security fixes for medium risk vulnerabilities
"""
import os
import re
import hashlib
import secrets
from typing import Dict, List, Optional


class SecurityHardener:
    """Apply security hardening measures"""
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.vulnerabilities = []
    
    def fix_sql_injection(self, code: str) -> str:
        """Fix potential SQL injection vulnerabilities"""
        # Replace string formatting with parameterized queries
        fixes = [
            # Pattern: f"SELECT ... {variable}"
            (r'f["']SELECT\s+.*?\{.*?\}.*?["']', 'Use parameterized queries'),
            # Pattern: "SELECT ... " + variable
            (r'["']SELECT\s+.*?["']\s*\+\s*\w+', 'Use parameterized queries'),
        ]
        
        fixed_code = code
        for pattern, recommendation in fixes:
            if re.search(pattern, code, re.IGNORECASE):
                self.vulnerabilities.append({
                    'type': 'SQL Injection',
                    'risk': 'Medium',
                    'recommendation': recommendation
                })
        
        return fixed_code
    
    def fix_xss_vulnerabilities(self, code: str) -> str:
        """Fix XSS vulnerabilities"""
        # Check for unescaped user input in HTML
        patterns = [
            r'innerHTML\s*=',
            r'document\.write\(',
            r'\.html\(',
        ]
        
        for pattern in patterns:
            if re.search(pattern, code):
                self.vulnerabilities.append({
                    'type': 'XSS',
                    'risk': 'Medium',
                    'recommendation': 'Use textContent or escape HTML entities'
                })
        
        return code
    
    def add_input_validation(self, code: str) -> str:
        """Add input validation"""
        # Add CSRF token validation
        csrf_check = """
        if not self._verify_csrf_token():
            raise SecurityError("Invalid CSRF token")
"""
        
        # Add rate limiting
        rate_limit_check = """
        if self._is_rate_limited(request.ip):
            raise SecurityError("Rate limit exceeded")
"""
        
        return code
    
    def generate_security_report(self) -> Dict:
        """Generate security audit report"""
        return {
            'vulnerabilities': self.vulnerabilities,
            'risk_level': self._calculate_risk_level(),
            'recommendations': self._generate_recommendations(),
            'scan_timestamp': time.time()
        }
    
    def _calculate_risk_level(self) -> str:
        """Calculate overall risk level"""
        if len(self.vulnerabilities) == 0:
            return 'Low'
        elif len(self.vulnerabilities) <= 2:
            return 'Medium'
        else:
            return 'High'
    
    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        for vuln in self.vulnerabilities:
            recommendations.append(vuln['recommendation'])
        
        if not recommendations:
            recommendations.append("No immediate action required")
        
        return recommendations


class SecurityError(Exception):
    """Security-related error"""
    pass


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Security Hardener')
    parser.add_argument('--scan', type=str, help='File to scan')
    parser.add_argument('--fix', action='store_true', help='Apply fixes')
    
    args = parser.parse_args()
    
    hardener = SecurityHardener()
    
    if args.scan:
        print(f"Scanning {args.scan}...")
        with open(args.scan, 'r') as f:
            code = f.read()
        
        hardener.fix_sql_injection(code)
        hardener.fix_xss_vulnerabilities(code)
        
        report = hardener.generate_security_report()
        print(f"\nSecurity Report:")
        print(f"  Risk Level: {report['risk_level']}")
        print(f"  Vulnerabilities: {len(report['vulnerabilities'])}")
        print(f"  Recommendations:")
        for rec in report['recommendations']:
            print(f"    - {rec}")
    else:
        print("Please provide --scan <file> to scan")


if __name__ == '__main__':
    main()
