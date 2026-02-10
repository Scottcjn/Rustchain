import json
import platform
import sys
import os
import click

# Add parent or sibling directory to path if needed to find fingerprint_checks
sys.path.append(os.path.join(os.path.dirname(__file__), '../../miners/linux'))

try:
    from fingerprint_checks import validate_all_checks
except ImportError:
    click.echo("Error: fingerprint_checks.py not found in miners/linux/")
    sys.exit(1)

@click.command()
@click.option('--json-output', is_flag=True, help="Export results as JSON.")
def test_runner(json_output):
    """Standardized test suite for RustChain hardware fingerprints."""
    click.echo("--- RustChain Preflight Validator ---")
    click.echo(f"Platform: {platform.system()} ({platform.machine()})")
    click.echo("Running 6 hardware fingerprint checks...\n")

    passed, results = validate_all_checks()

    if json_output:
        click.echo(json.dumps({"passed": passed, "results": results}, indent=2))
        return

    # Human-readable output
    for name, data in results.items():
        status = "✅ PASS" if data.get("passed") else "❌ FAIL"
        click.echo(f"[{status}] {name.replace('_', ' ').title()}")
        if not data.get("passed"):
            click.echo(f"   Diagnostic: {data.get('data')}")

    click.echo("\n" + "="*40)
    if passed:
        click.echo("OVERALL RESULT: ✅ VALID HARDWARE")
        click.echo("Your machine is eligible for full mining rewards.")
    else:
        click.echo("OVERALL RESULT: ❌ INCONSISTENT FINGERPRINT")
        click.echo("Warning: VM/Container detected or clock drift too low.")
    click.echo("="*40)

if __name__ == "__main__":
    test_runner()
