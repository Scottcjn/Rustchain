#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Validation script for BCOS Badge Generator (static HTML/JS).

Performs file checks to ensure the badge generator is properly configured.

Usage:
    python validate_bcos_generator.py
"""

import os
import re
import sys
from pathlib import Path


def check_file_exists(filepath: str) -> bool:
    """Check if file exists."""
    exists = os.path.isfile(filepath)
    status = "✓" if exists else "✗"
    print(f"  {status} File exists: {filepath}")
    return exists


def check_file_size(filepath: str, min_size: int = 1000) -> bool:
    """Check if file has minimum size."""
    try:
        size = os.path.getsize(filepath)
        ok = size >= min_size
        status = "✓" if ok else "✗"
        print(f"  {status} File size: {size} bytes (min: {min_size})")
        return ok
    except OSError as e:
        print(f"  ✗ File size check failed: {e}")
        return False


def check_html_structure(filepath: str) -> bool:
    """Check for required HTML structure."""
    required_elements = [
        r'<!DOCTYPE\s+html',
        r'<html[^>]*lang="en"',
        r'<head>',
        r'<meta\s+charset="UTF-8"',
        r'<meta\s+name="viewport"',
        r'<title>.*BCOS.*Badge.*Generator</title>',
        r'</head>',
        r'<body>',
        r'</body>',
        r'</html>',
    ]

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        all_ok = True
        for pattern in required_elements:
            match = re.search(pattern, content, re.IGNORECASE)
            ok = match is not None
            status = "✓" if ok else "✗"
            element_name = pattern.split(r'\s+')[0].strip('<[]')
            print(f"  {status} HTML element: {element_name}")
            if not ok:
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"  ✗ HTML structure check failed: {e}")
        return False


def check_required_components(filepath: str) -> bool:
    """Check for required UI components."""
    required = [
        (r'id="certId"', 'Certificate ID input'),
        (r'id="inputType"', 'Input type selector'),
        (r'data-style="flat"', 'Flat style option'),
        (r'data-style="flat-square"', 'Flat-square style option'),
        (r'data-style="for-the-badge"', 'For-the-badge style option'),
        (r'id="previewArea"', 'Preview area'),
        (r'id="badgeForm"', 'Badge form'),
        (r'id="markdownCode"', 'Markdown output'),
        (r'id="htmlCode"', 'HTML output'),
        (r'const BADGE_ENDPOINT', 'Badge endpoint config'),
        (r'const VERIFY_BASE_URL', 'Verify URL config'),
        (r'async function generateBadge', 'Generate function'),
        (r'function generateEmbedCodes', 'Embed code generator'),
    ]

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        all_ok = True
        for pattern, description in required:
            ok = re.search(pattern, content) is not None
            status = "✓" if ok else "✗"
            print(f"  {status} Component: {description}")
            if not ok:
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"  ✗ Component check failed: {e}")
        return False


def check_javascript_syntax(filepath: str) -> bool:
    """Basic JavaScript syntax check (balanced braces, etc.)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract JavaScript from <script> tags
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, content, re.DOTALL)

        if not scripts:
            print("  ✗ No JavaScript found")
            return False

        all_ok = True
        for i, script in enumerate(scripts):
            # Check balanced braces
            open_braces = script.count('{')
            close_braces = script.count('}')
            braces_ok = open_braces == close_braces
            status = "✓" if braces_ok else "✗"
            print(f"  {status} JS block {i+1}: balanced braces ({open_braces} open, {close_braces} close)")
            if not braces_ok:
                all_ok = False

            # Check balanced parentheses
            open_parens = script.count('(')
            close_parens = script.count(')')
            parens_ok = open_parens == close_parens
            status = "✓" if parens_ok else "✗"
            print(f"  {status} JS block {i+1}: balanced parentheses ({open_parens} open, {close_parens} close)")
            if not parens_ok:
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"  ✗ JavaScript syntax check failed: {e}")
        return False


def check_css_syntax(filepath: str) -> bool:
    """Basic CSS syntax check (balanced braces)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract CSS from <style> tags
        style_pattern = r'<style[^>]*>(.*?)</style>'
        styles = re.findall(style_pattern, content, re.DOTALL)

        if not styles:
            print("  ✗ No CSS found")
            return False

        all_ok = True
        for i, style in enumerate(styles):
            # Check balanced braces
            open_braces = style.count('{')
            close_braces = style.count('}')
            braces_ok = open_braces == close_braces
            status = "✓" if braces_ok else "✗"
            print(f"  {status} CSS block {i+1}: balanced braces ({open_braces} open, {close_braces} close)")
            if not braces_ok:
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"  ✗ CSS syntax check failed: {e}")
        return False


def check_embed_format(filepath: str) -> bool:
    """Check that embed code format matches requirements."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for exact markdown format: [![BCOS](...)](...)
        markdown_pattern = r'\[\!\[BCOS\]\([^)]+\)\]\([^)]+\)'
        markdown_ok = re.search(markdown_pattern, content) is not None
        status = "✓" if markdown_ok else "✗"
        print(f"  {status} Markdown embed format: [![BCOS](...)](...)")

        # Check for HTML img tag pattern
        html_pattern = r'<img\s+src=.*alt=.*BCOS'
        html_ok = re.search(html_pattern, content, re.IGNORECASE) is not None
        status = "✓" if html_ok else "✗"
        print(f"  {status} HTML embed format: <img> tag with BCOS alt")

        return markdown_ok and html_ok
    except Exception as e:
        print(f"  ✗ Embed format check failed: {e}")
        return False


def check_terminal_aesthetic(filepath: str) -> bool:
    """Check for vintage terminal aesthetic elements."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        terminal_elements = [
            ('Courier New', 'Monospace font'),
            ('--term-', 'Terminal color variables'),
            ('terminal-window', 'Terminal window class'),
            ('terminal-header', 'Terminal header class'),
            ('ascii-art', 'ASCII art decoration'),
        ]

        all_ok = True
        for pattern, description in terminal_elements:
            ok = pattern in content
            status = "✓" if ok else "✗"
            print(f"  {status} Terminal aesthetic: {description}")
            if not ok:
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"  ✗ Terminal aesthetic check failed: {e}")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("BCOS Badge Generator — Validation")
    print("=" * 60)

    # Determine file path
    script_dir = Path(__file__).parent
    index_file = script_dir / 'bcos-badge-generator' / 'index.html'

    if not index_file.exists():
        # Try relative to current directory
        index_file = Path('tools/bcos-badge-generator/index.html')

    index_file_str = str(index_file)

    print(f"\nTarget file: {index_file_str}\n")

    results = []

    print("1. File Checks")
    print("-" * 40)
    results.append(check_file_exists(index_file_str))
    results.append(check_file_size(index_file_str))

    print("\n2. HTML Structure")
    print("-" * 40)
    results.append(check_html_structure(index_file_str))

    print("\n3. Required Components")
    print("-" * 40)
    results.append(check_required_components(index_file_str))

    print("\n4. JavaScript Syntax")
    print("-" * 40)
    results.append(check_javascript_syntax(index_file_str))

    print("\n5. CSS Syntax")
    print("-" * 40)
    results.append(check_css_syntax(index_file_str))

    print("\n6. Embed Code Format")
    print("-" * 40)
    results.append(check_embed_format(index_file_str))

    print("\n7. Terminal Aesthetic")
    print("-" * 40)
    results.append(check_terminal_aesthetic(index_file_str))

    print("\n" + "=" * 60)
    if all(results):
        print("✓ All validation checks passed!")
        print("=" * 60)
        return 0
    else:
        failed_count = len(results) - sum(results)
        print(f"✗ {failed_count} validation check(s) failed")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
