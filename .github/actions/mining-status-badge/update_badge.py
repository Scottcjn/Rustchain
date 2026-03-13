#!/usr/bin/env python3
"""
RustChain Mining Status Badge Updater
======================================

GitHub Action script that updates the mining status badge in README.md.

Purpose:
    - Automatically update Shields.io badge URL with current wallet address
    - Support custom badge styles via environment variables
    - Insert or replace badge in README with HTML comments as markers

Integration:
    Used in GitHub Actions workflow to ensure README badge stays in sync
    with the configured wallet address.

Environment Variables:
    WALLET: RustChain miner wallet address (default: "frozen-factorio-ryan")
    STYLE: Shields.io badge style (default: "flat-square")
            Options: flat, flat-square, plastic, for-the-badge, etc.

Usage:
    # Basic usage (reads WALLET and STYLE from env)
    python3 update_badge.py
    
    # Custom README path
    python3 update_badge.py path/to/README.md
    
    # With environment variables
    WALLET=my-wallet STYLE=flat python3 update_badge.py

Badge Format:
    The badge is wrapped in HTML comments for easy identification:
    <!-- rustchain-mining-badge-start -->
    ![RustChain Mining Status](https://img.shields.io/endpoint?url=...)
    <!-- rustchain-mining-badge-end -->

Author: Elyan Labs
Date: 2026-03
"""

import os
import sys
from pathlib import Path
from typing import Optional


def update_badge(
    readme_path: str = "README.md",
    wallet: Optional[str] = None,
    style: Optional[str] = None
) -> bool:
    """
    Update mining status badge in README file.
    
    Args:
        readme_path: Path to README.md file (default: "README.md")
        wallet: RustChain wallet address (default: from WALLET env var)
        style: Badge style (default: from STYLE env var)
    
    Returns:
        bool: True if successful, False if file not found or error
    
    Side Effects:
        - Modifies README.md in place
        - Prints status message to stdout
    
    Badge Markers:
        Uses HTML comments to identify badge location:
        <!-- rustchain-mining-badge-start -->
        <!-- rustchain-mining-badge-end -->
    
    Behavior:
        - If markers exist: Replace content between markers
        - If markers missing: Append new "## Mining Status" section
        - Preserves rest of README content unchanged
    
    Example:
        >>> success = update_badge("README.md", wallet="my-wallet", style="flat")
        Updated README.md with mining badge for wallet: my-wallet
    """
    # Get configuration from environment or parameters
    wallet = wallet or os.environ.get("WALLET", "frozen-factorio-ryan")
    style = style or os.environ.get("STYLE", "flat-square")
    
    readme = Path(readme_path)
    
    # Check if README exists
    if not readme.exists():
        print(f"❌ README not found: {readme_path}")
        return False
    
    # Read current README content
    try:
        text = readme.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        print(f"❌ Failed to read README (encoding error): {e}")
        return False
    
    # Badge markers (HTML comments for easy identification)
    start_marker = "<!-- rustchain-mining-badge-start -->"
    end_marker = "<!-- rustchain-mining-badge-end -->"
    
    # Build badge markdown with Shields.io endpoint
    badge_url = f"https://img.shields.io/endpoint?url=https://rustchain.org/api/badge/{wallet}&style={style}"
    badge_block = f"{start_marker}\n![RustChain Mining Status]({badge_url})\n{end_marker}"
    
    # Find existing badge markers
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    
    # Update or insert badge
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        # Replace existing badge (preserve content before and after)
        new_text = text[:start_idx] + badge_block + text[end_idx + len(end_marker):]
        print(f"🔄 Replaced existing mining badge in {readme_path}")
    else:
        # Insert new badge section at end of file
        new_text = text.rstrip() + "\n\n## Mining Status\n" + badge_block + "\n"
        print(f"➕ Added new mining badge section to {readme_path}")
    
    # Write updated content back to README
    try:
        readme.write_text(new_text, encoding="utf-8")
        print(f"✅ Updated {readme_path} with mining badge for wallet: {wallet}")
        print(f"   Style: {style}")
        print(f"   Badge URL: {badge_url}")
        return True
    except IOError as e:
        print(f"❌ Failed to write README: {e}")
        return False


def main() -> None:
    """
    Main entry point for CLI usage.
    
    Command-line Arguments:
        readme_path: Optional path to README.md (default: "README.md")
    
    Environment Variables:
        WALLET: Miner wallet address (default: "frozen-factorio-ryan")
        STYLE: Badge style (default: "flat-square")
    
    Exit Codes:
        0: Success
        1: File not found or error
    """
    # Get README path from command-line argument or use default
    readme_path: str = sys.argv[1] if len(sys.argv) > 1 else "README.md"
    
    # Update badge and exit with appropriate code
    success = update_badge(readme_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
