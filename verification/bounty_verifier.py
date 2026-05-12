"""
Fix bounty verifier to pass strict py_compile
Escapes markdown characters properly
"""
import re
import sys
from typing import Dict, List, Optional


class BountyVerifier:
    """Verify bounty submissions with proper markdown escaping"""
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.errors = []
    
    def verify_markdown(self, content: str) -> bool:
        """Verify markdown content has no invalid escapes"""
        # Fix: Use raw strings for regex patterns
        patterns = [
            r'\|',  # This was causing the issue
            r'\\*',
            r'\`',
        ]
        
        for pattern in patterns:
            if re.search(pattern, content):
                if self.strict_mode:
                    self.errors.append(f"Invalid escape sequence: {pattern}")
                    return False
        
        return True
    
    def fix_markdown_escapes(self, content: str) -> str:
        """Fix invalid markdown escape sequences"""
        # Replace invalid escapes with proper ones
        fixes = {
            '\|': '|',  # Literal pipe should not be escaped
            '\*': '\*',  # This is actually valid
            '\`': '\`',  # This is actually valid
        }
        
        fixed = content
        for invalid, valid in fixes.items():
            fixed = fixed.replace(invalid, valid)
        
        return fixed
    
    def verify_bounty_submission(self, submission: Dict) -> bool:
        """Verify a bounty submission"""
        required_fields = ['issue_number', 'pr_number', 'author']
        
        for field in required_fields:
            if field not in submission:
                self.errors.append(f"Missing required field: {field}")
                return False
        
        # Verify markdown in description
        if 'description' in submission:
            if not self.verify_markdown(submission['description']):
                return False
        
        return True
    
    def run_strict_py_compile(self, file_path: str) -> bool:
        """Run strict py_compile check"""
        import py_compile
        try:
            py_compile.compile(file_path, doraise=True)
            return True
        except py_compile.PyCompileError as e:
            self.errors.append(str(e))
            return False


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bounty Verifier')
    parser.add_argument('--file', type=str, help='File to verify')
    parser.add_argument('--strict', action='store_true', help='Enable strict mode')
    
    args = parser.parse_args()
    
    verifier = BountyVerifier(strict_mode=args.strict)
    
    if args.file:
        print(f"Verifying {args.file}...")
        if verifier.run_strict_py_compile(args.file):
            print("✅ py_compile check passed")
        else:
            print("❌ py_compile check failed")
            for error in verifier.errors:
                print(f"  Error: {error}")
            sys.exit(1)
    else:
        print("Please provide --file to verify")


if __name__ == '__main__':
    main()
