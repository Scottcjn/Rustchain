import os
import re

def test_no_hardcoded_flask_debug():
    """
    Regression test to ensure no Flask entrypoints hardcode debug=True.
    Safe practice is to use an environment variable.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    affected_files = [
        'security_test_payment_widget.py',
        'profile_badge_generator.py',
        'xss_poc_templates.py',
        'keeper_explorer.py',
        'contributor_registry.py',
        'bridge/bridge_api.py',
        'explorer/app.py'
    ]

    pattern = re.compile(r'app\.run\(.*debug\s*=\s*True', re.IGNORECASE)

    errors = []
    for rel_path in affected_files:
        full_path = os.path.join(base_dir, rel_path)
        if not os.path.exists(full_path):
            continue

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if pattern.search(content):
                errors.append(f"Hardcoded debug=True found in {rel_path}")

    if errors:
        print("\n".join(errors))
        exit(1)

if __name__ == "__main__":
    test_no_hardcoded_flask_debug()
    print("Test passed: No hardcoded debug=True found.")
