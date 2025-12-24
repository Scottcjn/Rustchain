#!/usr/bin/env python3
"""
Apply admin authentication fix to RustChain production code
Adds @admin_required decorator to unprotected OUI admin endpoints
"""

import sys

def apply_fix(filepath):
    """Add @admin_required decorators to OUI admin endpoints"""

    with open(filepath, 'r') as f:
        lines = f.readlines()

    fixed_lines = []
    fixes_applied = 0

    for i, line in enumerate(lines):
        # Check if this line is an unprotected admin route
        if line.strip().startswith("@app.route('/admin/oui_deny/"):
            # Check if next line is already @admin_required
            if i+1 < len(lines) and '@admin_required' not in lines[i+1]:
                # Insert @admin_required decorator
                fixed_lines.append(line)
                fixed_lines.append("@admin_required\n")
                fixes_applied += 1
                print(f"✓ Added @admin_required before {line.strip()}")
                continue

        fixed_lines.append(line)

    if fixes_applied > 0:
        # Write fixed version
        with open(filepath, 'w') as f:
            f.writelines(fixed_lines)
        print(f"\n✅ Applied {fixes_applied} fixes to {filepath}")
        return True
    else:
        print("⚠️  No fixes needed (already protected or different structure)")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 apply_admin_auth_fix.py <file>")
        sys.exit(1)

    filepath = sys.argv[1]
    print("="*80)
    print("RustChain Admin Authentication Fix")
    print("="*80)
    print(f"\nTarget file: {filepath}\n")

    success = apply_fix(filepath)

    if success:
        print("\n🔒 Admin endpoints now require authentication!")
        print("    Use header: X-API-Key: <RC_ADMIN_KEY>")

    print("="*80)
