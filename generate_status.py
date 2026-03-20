#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
CLI script to generate status.html from live network data.
Uses network_status_generator.py to fetch current data and create a deployable HTML file.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

try:
    from network_status_generator import RustChainStatusGenerator
except ImportError:
    print("Error: network_status_generator.py not found in current directory")
    sys.exit(1)


def setup_logging(verbose=False):
    """Configure logging output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=level
    )


def save_html_file(html_content, output_path):
    """Save HTML content to file with proper encoding."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return True
    except Exception as e:
        logging.error(f"Failed to write HTML file: {e}")
        return False


def save_json_data(data, output_path):
    """Save raw network data as JSON for debugging."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logging.error(f"Failed to write JSON file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate RustChain network status page from live data"
    )
    parser.add_argument(
        '--output', '-o',
        default='status.html',
        help='Output HTML file path (default: status.html)'
    )
    parser.add_argument(
        '--json-output',
        help='Also save raw data as JSON to this path'
    )
    parser.add_argument(
        '--node-url',
        default='https://50.28.86.131',
        help='RustChain node URL (default: https://50.28.86.131)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite output file if it exists'
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Check if output file exists
    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        print(f"Error: {args.output} already exists. Use --force to overwrite.")
        sys.exit(1)

    logging.info(f"Generating status page from {args.node_url}")

    # Initialize status generator
    generator = RustChainStatusGenerator(
        node_url=args.node_url,
        request_timeout=args.timeout
    )

    # Fetch network data
    try:
        network_data = generator.fetch_network_data()
    except Exception as e:
        logging.error(f"Failed to fetch network data: {e}")
        sys.exit(1)

    if not network_data:
        logging.error("No network data retrieved")
        sys.exit(1)

    # Generate HTML
    try:
        html_content = generator.generate_status_page(network_data)
    except Exception as e:
        logging.error(f"Failed to generate HTML: {e}")
        sys.exit(1)

    # Save HTML file
    if save_html_file(html_content, args.output):
        logging.info(f"Status page saved to {args.output}")
        print(f"✓ Generated: {args.output}")
    else:
        sys.exit(1)

    # Save JSON data if requested
    if args.json_output:
        if save_json_data(network_data, args.json_output):
            logging.info(f"Raw data saved to {args.json_output}")
            print(f"✓ Data saved: {args.json_output}")
        else:
            logging.warning("Failed to save JSON data")

    # Display summary
    miners = network_data.get('miners', [])
    active_miners = len([m for m in miners if m.get('status') == 'active'])
    total_miners = len(miners)

    print(f"\nNetwork Summary:")
    print(f"  Active miners: {active_miners}/{total_miners}")
    print(f"  Node status: {network_data.get('node_status', 'unknown')}")
    print(f"  Last updated: {network_data.get('timestamp', 'unknown')}")


if __name__ == '__main__':
    main()
