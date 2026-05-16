#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
BCOS v2 Badge Generator — Web tool for generating BCOS certification badges.

Generates dynamic SVG badges for BCOS-certified repositories with:
- Tier-based styling (L0/L1/L2)
- Trust score visualization
- Certificate ID embedding
- QR code generation for verification
- Export to PNG/SVG/Markdown

Usage:
    python bcos_badge_generator.py [--port 5000] [--host 0.0.0.0]

API Endpoints:
    GET  /                           - Badge generator UI
    POST /api/badge/generate         - Generate badge SVG
    POST /api/badge/verify           - Verify BCOS certificate
    GET  /api/badge/<cert_id>/svg    - Get badge SVG by cert ID
    GET  /api/badge/stats            - Get badge statistics
    GET  /health                     - Health check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Try to import Flask, provide helpful error if missing
try:
    from flask import Flask, render_template_string, request, jsonify, send_from_directory
except ImportError:
    print("Flask not installed. Install with: pip install flask", file=sys.stderr)
    sys.exit(1)

# Initialize Flask app
def _get_persistent_secret_key(env_var: str, path: str = ".flask_directory_key") -> str:
    """Persist Flask secret key across restarts."""
    key = os.environ.get(env_var, "").strip()
    if key:
        return key
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    key = os.urandom(32).hex()
    with open(path, "w") as f:
        f.write(key)
    os.chmod(path, 0o600)
    return key

app = Flask(__name__)
app.config['SECRET_KEY'] = _get_persistent_secret_key('BCOS_BADGE_SECRET_KEY', '.flask_badge_key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Database path
DATABASE = 'bcos_badges.db'

# ── Badge Configuration ──────────────────────────────────────────────

BADGE_CONFIG = {
    'tiers': {
        'L0': {
            'label': 'Basic',
            'color_start': '#555555',
            'color_end': '#4c1',
            'bg_color': '#e8f5e8',
            'text_color': '#2d8f2d',
            'min_score': 40,
        },
        'L1': {
            'label': 'Verified',
            'color_start': '#667eea',
            'color_end': '#764ba2',
            'bg_color': '#eef2ff',
            'text_color': '#667eea',
            'min_score': 60,
        },
        'L2': {
            'label': 'Certified',
            'color_start': '#f093fb',
            'color_end': '#f5576c',
            'bg_color': '#fef2f2',
            'text_color': '#c53030',
            'min_score': 80,
        },
    },
    'width': 140,
    'height': 24,
    'font_family': 'Verdana, Geneva, sans-serif',
    'font_size': 11,
}

# ── Database Functions ──────────────────────────────────────────────


def init_db():
    """Initialize SQLite database for badge tracking."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Badges table
    c.execute('''
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_id TEXT UNIQUE NOT NULL,
            repo_name TEXT NOT NULL,
            github_url TEXT NOT NULL,
            tier TEXT NOT NULL,
            trust_score INTEGER NOT NULL,
            commitment TEXT,
            reviewer TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            download_count INTEGER DEFAULT 0,
            verification_url TEXT,
            sbom_hash TEXT,
            metadata JSON
        )
    ''')

    # Verification cache table
    c.execute('''
        CREATE TABLE IF NOT EXISTS verification_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_id TEXT UNIQUE NOT NULL,
            is_valid BOOLEAN NOT NULL,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            response_data JSON,
            ttl INTEGER DEFAULT 3600
        )
    ''')

    # Badge generation analytics
    c.execute('''
        CREATE TABLE IF NOT EXISTS badge_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            cert_id TEXT,
            repo_name TEXT,
            tier TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON
        )
    ''')

    conn.commit()
    conn.close()


def record_badge_generation(cert_id: str, repo_name: str, tier: str, metadata: Dict = None):
    """Record badge generation in database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''
        INSERT INTO badges (cert_id, repo_name, github_url, tier, trust_score, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        cert_id,
        repo_name,
        f"https://github.com/{repo_name}",
        tier,
        metadata.get('trust_score', 0) if metadata else 0,
        json.dumps(metadata or {})
    ))

    # Record analytics
    c.execute('''
        INSERT INTO badge_analytics (event_type, cert_id, repo_name, tier, metadata)
        VALUES (?, ?, ?, ?, ?)
    ''', ('generate', cert_id, repo_name, tier, json.dumps(metadata or {})))

    conn.commit()
    conn.close()


def increment_download_count(cert_id: str):
    """Increment download count for a badge."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        UPDATE badges SET download_count = download_count + 1
        WHERE cert_id = ?
    ''', (cert_id,))
    conn.commit()
    conn.close()


def get_badge_stats() -> Dict:
    """Get badge generation statistics."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Total badges
    c.execute('SELECT COUNT(*) FROM badges')
    total = c.fetchone()[0]

    # By tier
    c.execute('SELECT tier, COUNT(*) FROM badges GROUP BY tier')
    by_tier = dict(c.fetchall())

    # Recent generations (last 7 days)
    c.execute('''
        SELECT COUNT(*) FROM badges
        WHERE generated_at >= datetime('now', '-7 days')
    ''')
    recent = c.fetchone()[0]

    # Top repos
    c.execute('''
        SELECT repo_name, COUNT(*) as cnt FROM badges
        GROUP BY repo_name ORDER BY cnt DESC LIMIT 10
    ''')
    top_repos = c.fetchall()

    conn.close()

    return {
        'total_badges': total,
        'by_tier': by_tier,
        'recent_7_days': recent,
        'top_repos': [{'repo': r[0], 'count': r[1]} for r in top_repos],
    }


# ── Badge SVG Generation ──────────────────────────────────────────────


def generate_badge_svg(
    repo_name: str,
    tier: str = 'L1',
    trust_score: int = 75,
    cert_id: str = '',
    include_qr: bool = False,
    verification_url: str = '',
) -> str:
    """
    Generate SVG badge for BCOS certification.

    Args:
        repo_name: Repository name (owner/repo)
        tier: BCOS tier (L0, L1, L2)
        trust_score: Trust score 0-100
        cert_id: Certificate ID (BCOS-xxxxxxxx)
        include_qr: Include QR code for verification
        verification_url: URL for QR code

    Returns:
        SVG content as string
    """
    config = BADGE_CONFIG['tiers'].get(tier, BADGE_CONFIG['tiers']['L1'])
    width = BADGE_CONFIG['width']
    height = BADGE_CONFIG['height']

    # Truncate repo name if too long
    display_name = repo_name
    if len(display_name) > 25:
        display_name = display_name[:22] + '...'

    # QR code section (optional)
    qr_section = ''
    qr_width = 0
    if include_qr and verification_url:
        qr_width = 80
        width += qr_width + 10
        # Simple QR-like pattern (placeholder - in production use qrcode library)
        qr_section = f'''
  <g transform="translate({width - qr_width - 5}, 2)">
    <rect width="{qr_width - 4}" height="{height - 4}" fill="white" stroke="{config['color_start']}" stroke-width="1"/>
    <rect x="4" y="4" width="8" height="8" fill="{config['color_start']}"/>
    <rect x="{qr_width - 16}" y="4" width="8" height="8" fill="{config['color_start']}"/>
    <rect x="4" y="{height - 12}" width="8" height="8" fill="{config['color_start']}"/>
    <rect x="16" y="16" width="4" height="4" fill="{config['color_start']}"/>
    <rect x="24" y="8" width="4" height="4" fill="{config['color_start']}"/>
    <rect x="32" y="16" width="4" height="4" fill="{config['color_start']}"/>
    <rect x="12" y="2" width="2" height="2" fill="{config['color_start']}"/>
    <text x="42" y="14" font-family="Arial" font-size="6" fill="{config['color_start']}">SCAN</text>
  </g>
'''

    # Trust score bar (mini visualization)
    score_bar_width = 40
    score_fill = int(trust_score / 100 * score_bar_width)
    score_color = '#4c1' if trust_score >= 80 else '#f59e0b' if trust_score >= 60 else '#ef4444'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" aria-label="BCOS {tier} Certified: {repo_name}">
  <defs>
    <linearGradient id="bcos_grad_{tier}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{config['color_start']};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{config['color_end']};stop-opacity:1" />
    </linearGradient>
    <clipPath id="badge_clip">
      <rect width="{width}" height="{height}" rx="3"/>
    </clipPath>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="url(#bcos_grad_{tier})" rx="3"/>

  <!-- BCOS label -->
  <text x="8" y="16" font-family="{BADGE_CONFIG['font_family']}" font-size="{BADGE_CONFIG['font_size']}" font-weight="bold" fill="white">BCOS</text>

  <!-- Tier badge -->
  <rect x="48" y="4" width="24" height="14" rx="2" fill="white" fill-opacity="0.25"/>
  <text x="60" y="15" font-family="{BADGE_CONFIG['font_family']}" font-size="9" font-weight="bold" fill="white">{tier}</text>

  <!-- Trust score indicator -->
  <rect x="78" y="8" width="{score_bar_width}" height="6" rx="2" fill="white" fill-opacity="0.2"/>
  <rect x="79" y="9" width="{score_fill}" height="4" rx="1" fill="{score_color}"/>

  <!-- Repo name -->
  <text x="125" y="16" font-family="{BADGE_CONFIG['font_family']}" font-size="9" fill="white" opacity="0.9">{display_name}</text>

  {qr_section}
</svg>'''

    return svg


def generate_static_badge_svg(tier: str = 'L1') -> str:
    """Generate a simple static badge without dynamic content."""
    config = BADGE_CONFIG['tiers'].get(tier, BADGE_CONFIG['tiers']['L1'])
    label = config['label']

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="120" height="20">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{config['color_start']};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{config['color_end']};stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="120" height="20" fill="url(#grad)" rx="3"/>
  <text x="10" y="14" font-family="Verdana, Geneva, sans-serif" font-size="11" fill="white">BCOS {label}</text>
</svg>'''

    return svg


# ── Certificate Verification ──────────────────────────────────────────────


def verify_certificate(cert_id: str, use_cache: bool = True) -> Dict:
    """
    Verify a BCOS certificate.

    In production, this would query the RustChain blockchain or
    a verification service. For now, we check local database.
    """
    # Check cache first
    if use_cache:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            SELECT is_valid, response_data, verified_at, ttl
            FROM verification_cache
            WHERE cert_id = ?
            AND datetime(verified_at, '+' || ttl || ' seconds') > datetime('now')
        ''', (cert_id,))
        cached = c.fetchone()
        conn.close()

        if cached:
            return {
                'valid': bool(cached[0]),
                'cached': True,
                'verified_at': cached[2],
                'data': json.loads(cached[3]) if cached[3] else {},
            }

    # Check local database
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT cert_id, repo_name, tier, trust_score, commitment, reviewer, generated_at, metadata
        FROM badges
        WHERE cert_id = ?
    ''', (cert_id,))
    result = c.fetchone()
    conn.close()

    if result:
        verification_data = {
            'cert_id': result[0],
            'repo_name': result[1],
            'tier': result[2],
            'trust_score': result[3],
            'commitment': result[4],
            'reviewer': result[5],
            'generated_at': result[6],
            'metadata': json.loads(result[7]) if result[7] else {},
        }

        # Cache the result
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO verification_cache
            (cert_id, is_valid, response_data, ttl)
            VALUES (?, ?, ?, ?)
        ''', (cert_id, True, json.dumps(verification_data), 3600))
        conn.commit()
        conn.close()

        return {
            'valid': True,
            'cached': False,
            'data': verification_data,
        }

    return {'valid': False, 'cached': False, 'data': {}}


# ── HTML Templates ──────────────────────────────────────────────


MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BCOS v2 Badge Generator</title>
    <style>
        :root {
            --primary: #667eea;
            --primary-dark: #5a67d8;
            --secondary: #764ba2;
            --success: #48bb78;
            --warning: #ed8936;
            --danger: #f56565;
            --gray-100: #f7fafc;
            --gray-200: #edf2f7;
            --gray-300: #e2e8f0;
            --gray-600: #4a5568;
            --gray-700: #2d3748;
            --gray-800: #1a202c;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }

        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 30px;
            margin-bottom: 30px;
        }

        .card-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--gray-800);
            margin-bottom: 8px;
        }

        .card-subtitle {
            color: var(--gray-600);
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            font-weight: 600;
            color: var(--gray-700);
            margin-bottom: 8px;
        }

        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid var(--gray-200);
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }

        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: var(--primary);
        }

        .form-group .hint {
            font-size: 13px;
            color: var(--gray-600);
            margin-top: 6px;
        }

        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
        }

        .btn:hover {
            background: var(--primary-dark);
        }

        .btn:active {
            transform: scale(0.98);
        }

        .btn-secondary {
            background: var(--gray-200);
            color: var(--gray-700);
        }

        .btn-secondary:hover {
            background: var(--gray-300);
        }

        .btn-success {
            background: var(--success);
        }

        .btn-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .badge-preview {
            background: var(--gray-100);
            border: 2px dashed var(--gray-300);
            border-radius: 8px;
            padding: 30px;
            text-align: center;
            margin: 20px 0;
        }

        .badge-preview img {
            max-width: 100%;
            height: auto;
        }

        .code-block {
            background: var(--gray-800);
            color: #f8f8f2;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 13px;
            margin: 10px 0;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }

        .stat-card {
            background: var(--gray-100);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }

        .stat-label {
            color: var(--gray-600);
            font-size: 14px;
            margin-top: 5px;
        }

        .tier-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .tier-card {
            padding: 20px;
            border-radius: 8px;
            border: 2px solid;
        }

        .tier-card.l0 {
            border-color: #4c1;
            background: #f0fff4;
        }

        .tier-card.l1 {
            border-color: #667eea;
            background: #f5f3ff;
        }

        .tier-card.l2 {
            border-color: #f5576c;
            background: #fff5f5;
        }

        .tier-card h4 {
            margin-bottom: 8px;
        }

        .tier-card p {
            font-size: 13px;
            opacity: 0.8;
        }

        .alert {
            padding: 16px;
            border-radius: 8px;
            margin: 20px 0;
        }

        .alert-info {
            background: #ebf8ff;
            border-left: 4px solid #4299e1;
            color: #2c5282;
        }

        .alert-success {
            background: #f0fff4;
            border-left: 4px solid #48bb78;
            color: #22543d;
        }

        .alert-error {
            background: #fff5f5;
            border-left: 4px solid #f56565;
            color: #742a2a;
        }

        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .hidden {
            display: none;
        }

        .tabs {
            display: flex;
            border-bottom: 2px solid var(--gray-200);
            margin-bottom: 20px;
        }

        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }

        .tab:hover {
            color: var(--primary);
        }

        .tab.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        footer {
            text-align: center;
            color: white;
            margin-top: 40px;
            opacity: 0.8;
        }

        footer a {
            color: white;
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏅 BCOS v2 Badge Generator</h1>
            <p>Generate certification badges for BCOS-verified repositories</p>
        </div>

        <div class="card">
            <h2 class="card-title">Generate Your Badge</h2>
            <p class="card-subtitle">Enter your repository details to create a BCOS certification badge</p>

            <form id="badgeForm">
                <div class="form-group">
                    <label for="repoName">Repository Name *</label>
                    <input
                        type="text"
                        id="repoName"
                        name="repoName"
                        placeholder="owner/repo"
                        required
                        pattern="[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+"
                    />
                    <div class="hint">Format: username/repository-name</div>
                </div>

                <div class="form-group">
                    <label for="tier">BCOS Tier *</label>
                    <select id="tier" name="tier" required>
                        <option value="L0">L0 - Basic (Score ≥40)</option>
                        <option value="L1" selected>L1 - Verified (Score ≥60)</option>
                        <option value="L2">L2 - Certified (Score ≥80)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="trustScore">Trust Score (0-100)</label>
                    <input
                        type="number"
                        id="trustScore"
                        name="trustScore"
                        min="0"
                        max="100"
                        value="75"
                    />
                    <div class="hint">Based on BCOS v2 verification engine results</div>
                </div>

                <div class="form-group">
                    <label for="certId">Certificate ID (optional)</label>
                    <input
                        type="text"
                        id="certId"
                        name="certId"
                        placeholder="BCOS-xxxxxxxx"
                        pattern="BCOS-[a-fA-F0-9]{8}"
                    />
                    <div class="hint">If provided, badge will link to verification page</div>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="includeQR" name="includeQR" />
                        Include QR Code for Verification
                    </label>
                </div>

                <div class="btn-group">
                    <button type="submit" class="btn">
                        <span id="btnText">Generate Badge</span>
                        <span id="btnLoading" class="loading hidden"></span>
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="resetForm()">Reset</button>
                </div>
            </form>

            <div id="result" class="hidden">
                <div class="alert alert-success">
                    ✅ Badge generated successfully!
                </div>

                <div class="badge-preview">
                    <h4>Preview</h4>
                    <div id="badgePreview"></div>
                </div>

                <div class="tabs">
                    <div class="tab active" onclick="switchTab('markdown')">Markdown</div>
                    <div class="tab" onclick="switchTab('html')">HTML</div>
                    <div class="tab" onclick="switchTab('svg')">SVG</div>
                </div>

                <div id="tab-markdown" class="tab-content active">
                    <div class="code-block" id="markdownCode"></div>
                    <button class="btn btn-secondary" onclick="copyToClipboard('markdownCode')">Copy</button>
                </div>

                <div id="tab-html" class="tab-content">
                    <div class="code-block" id="htmlCode"></div>
                    <button class="btn btn-secondary" onclick="copyToClipboard('htmlCode')">Copy</button>
                </div>

                <div id="tab-svg" class="tab-content">
                    <div class="code-block" id="svgCode" style="white-space: pre-wrap; word-break: break-all;"></div>
                    <div class="btn-group">
                        <button class="btn btn-secondary" onclick="copyToClipboard('svgCode')">Copy SVG</button>
                        <button class="btn btn-secondary" onclick="downloadSVG()">Download SVG</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2 class="card-title">BCOS Tiers</h2>
            <p class="card-subtitle">Understanding certification levels</p>

            <div class="tier-info">
                <div class="tier-card l0">
                    <h4>🥉 L0 - Basic</h4>
                    <p>Automated checks: license compliance, test evidence, basic security scans. Minimum score: 40</p>
                </div>
                <div class="tier-card l1">
                    <h4>🥈 L1 - Verified</h4>
                    <p>Agent review + evidence: Semgrep analysis, vulnerability scan, SBOM. Minimum score: 60</p>
                </div>
                <div class="tier-card l2">
                    <h4>🥇 L2 - Certified</h4>
                    <p>Human review required: Maintainer approval, signed attestation. Minimum score: 80</p>
                </div>
            </div>
        </div>

        <div class="card">
            <h2 class="card-title">Statistics</h2>
            <p class="card-subtitle">Badge generation metrics</p>

            <div class="stats-grid" id="statsGrid">
                <div class="stat-card">
                    <div class="stat-value" id="statTotal">--</div>
                    <div class="stat-label">Total Badges</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="statL0">--</div>
                    <div class="stat-label">L0 Badges</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="statL1">--</div>
                    <div class="stat-label">L1 Badges</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="statL2">--</div>
                    <div class="stat-label">L2 Badges</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2 class="card-title">Verify a Badge</h2>
            <p class="card-subtitle">Check if a BCOS certificate is valid</p>

            <form id="verifyForm">
                <div class="form-group">
                    <label for="verifyCertId">Certificate ID</label>
                    <div class="input-group" style="display: flex; gap: 10px;">
                        <input
                            type="text"
                            id="verifyCertId"
                            placeholder="BCOS-xxxxxxxx"
                            style="flex: 1;"
                        />
                        <button type="submit" class="btn">Verify</button>
                    </div>
                </div>
            </form>

            <div id="verifyResult" class="hidden"></div>
        </div>

        <footer>
            <p>Part of the <a href="https://rustchain.org">RustChain</a> ecosystem</p>
            <p>BCOS — Beacon Certified Open Source</p>
        </footer>
    </div>

    <script>
        let currentSVG = '';

        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            event.target.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
        }

        function copyToClipboard(elementId) {
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert('Copied to clipboard!');
            });
        }

        function downloadSVG() {
            const blob = new Blob([currentSVG], {type: 'image/svg+xml'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'bcos-badge.svg';
            a.click();
            URL.revokeObjectURL(url);
        }

        function resetForm() {
            document.getElementById('badgeForm').reset();
            document.getElementById('result').classList.add('hidden');
        }

        function loadStats() {
            fetch('/api/badge/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('statTotal').textContent = data.total_badges || 0;
                    document.getElementById('statL0').textContent = data.by_tier?.L0 || 0;
                    document.getElementById('statL1').textContent = data.by_tier?.L1 || 0;
                    document.getElementById('statL2').textContent = data.by_tier?.L2 || 0;
                });
        }

        document.getElementById('badgeForm').addEventListener('submit', function(e) {
            e.preventDefault();

            const btnText = document.getElementById('btnText');
            const btnLoading = document.getElementById('btnLoading');
            btnText.classList.add('hidden');
            btnLoading.classList.remove('hidden');

            const formData = {
                repo_name: document.getElementById('repoName').value,
                tier: document.getElementById('tier').value,
                trust_score: parseInt(document.getElementById('trustScore').value) || 75,
                cert_id: document.getElementById('certId').value || null,
                include_qr: document.getElementById('includeQR').checked,
            };

            fetch('/api/badge/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(formData),
            })
            .then(r => r.json())
            .then(data => {
                btnText.classList.remove('hidden');
                btnLoading.classList.add('hidden');

                if (data.success) {
                    document.getElementById('badgePreview').innerHTML = data.svg;
                    document.getElementById('markdownCode').textContent = data.markdown;
                    document.getElementById('htmlCode').textContent = data.html;
                    document.getElementById('svgCode').textContent = data.svg;
                    currentSVG = data.svg;
                    document.getElementById('result').classList.remove('hidden');
                    loadStats();
                } else {
                    alert('Error: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(err => {
                btnText.classList.remove('hidden');
                btnLoading.classList.add('hidden');
                alert('Error: ' + err.message);
            });
        });

        document.getElementById('verifyForm').addEventListener('submit', function(e) {
            e.preventDefault();

            const certId = document.getElementById('verifyCertId').value;
            fetch('/api/badge/verify/' + certId)
                .then(r => r.json())
                .then(data => {
                    const resultDiv = document.getElementById('verifyResult');
                    resultDiv.classList.remove('hidden');

                    if (data.valid) {
                        resultDiv.innerHTML = `
                            <div class="alert alert-success">
                                <strong>✅ Valid Certificate</strong><br>
                                <strong>Repo:</strong> ${data.data.repo_name}<br>
                                <strong>Tier:</strong> ${data.data.tier}<br>
                                <strong>Trust Score:</strong> ${data.data.trust_score}/100<br>
                                ${data.data.reviewer ? '<strong>Reviewer:</strong> ' + data.data.reviewer : ''}
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="alert alert-error">
                                <strong>❌ Invalid Certificate</strong><br>
                                This certificate ID was not found in our database.
                            </div>
                        `;
                    }
                });
        });

        // Load stats on page load
        loadStats();
    </script>
</body>
</html>
'''

# ── Flask Routes ──────────────────────────────────────────────


@app.route('/')
def index():
    """Serve the badge generator UI."""
    return render_template_string(MAIN_TEMPLATE)


@app.route('/api/badge/generate', methods=['POST'])
def generate_badge():
    """Generate a BCOS badge."""
    data = request.get_json()

    repo_name = data.get('repo_name', '').strip()
    tier = data.get('tier', 'L1').upper()
    trust_score = data.get('trust_score', 75)
    cert_id = data.get('cert_id', '')
    include_qr = data.get('include_qr', False)

    # Validation
    if not repo_name:
        return jsonify({'success': False, 'error': 'Repository name is required'})

    if not re.match(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$', repo_name):
        return jsonify({'success': False, 'error': 'Invalid repository format. Use: owner/repo'})

    if tier not in ['L0', 'L1', 'L2']:
        return jsonify({'success': False, 'error': 'Invalid tier. Must be L0, L1, or L2'})

    if not (0 <= trust_score <= 100):
        return jsonify({'success': False, 'error': 'Trust score must be between 0 and 100'})

    # Generate cert_id if not provided
    if not cert_id:
        hash_input = f"{repo_name}{tier}{trust_score}{time.time()}"
        cert_hash = hashlib.blake2b(hash_input.encode(), digest_size=32).hexdigest()
        cert_id = f"BCOS-{cert_hash[:8]}"

    # Generate SVG
    svg = generate_badge_svg(
        repo_name=repo_name,
        tier=tier,
        trust_score=trust_score,
        cert_id=cert_id,
        include_qr=include_qr,
        verification_url=f"https://rustchain.org/bcos/verify/{cert_id}",
    )

    # Record in database
    try:
        record_badge_generation(cert_id, repo_name, tier, {
            'trust_score': trust_score,
            'include_qr': include_qr,
        })
    except Exception as e:
        app.logger.error(f"Failed to record badge generation: {e}")

    # Generate embed codes
    verification_url = f"https://rustchain.org/bcos/verify/{cert_id}"
    svg_url = f"https://rustchain.org/bcos/badge/{cert_id}.svg"

    markdown = f'[![BCOS {tier} Certified]({svg_url})]({verification_url})'
    html = f'<a href="{verification_url}"><img src="{svg_url}" alt="BCOS {tier} Certified"></a>'

    return jsonify({
        'success': True,
        'cert_id': cert_id,
        'svg': svg,
        'markdown': markdown,
        'html': html,
        'verification_url': verification_url,
    })


@app.route('/api/badge/verify/<cert_id>', methods=['GET'])
def verify_badge(cert_id):
    """Verify a BCOS badge certificate."""
    result = verify_certificate(cert_id)
    return jsonify(result)


@app.route('/api/badge/stats', methods=['GET'])
def badge_stats():
    """Get badge generation statistics."""
    stats = get_badge_stats()
    return jsonify(stats)


@app.route('/badge/<cert_id>.svg', methods=['GET'])
def serve_badge_svg(cert_id):
    """Serve badge SVG by certificate ID."""
    # Look up badge in database
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT repo_name, tier, trust_score, metadata
        FROM badges
        WHERE cert_id = ?
    ''', (cert_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        return 'Badge not found', 404

    repo_name, tier, trust_score, metadata = result
    metadata_dict = json.loads(metadata) if metadata else {}

    # Increment download count
    increment_download_count(cert_id)

    # Generate SVG
    svg = generate_badge_svg(
        repo_name=repo_name,
        tier=tier,
        trust_score=trust_score,
        cert_id=cert_id,
        include_qr=metadata_dict.get('include_qr', False),
        verification_url=f"https://rustchain.org/bcos/verify/{cert_id}",
    )

    return svg, 200, {'Content-Type': 'image/svg+xml'}


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'bcos-badge-generator',
        'version': '2.0.0',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


# ── CLI ──────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description='BCOS v2 Badge Generator - Generate certification badges for BCOS-verified repositories'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to run the server on (default: 5000)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    args = parser.parse_args()

    # Initialize database
    init_db()

    print(f"""
╔══════════════════════════════════════════════════╗
║  BCOS v2 Badge Generator                         ║
╚══════════════════════════════════════════════════╝

Starting server on http://{args.host}:{args.port}

Endpoints:
  GET  /                    - Badge generator UI
  POST /api/badge/generate  - Generate badge
  GET  /api/badge/verify/<id> - Verify certificate
  GET  /api/badge/stats     - Get statistics
  GET  /badge/<id>.svg      - Download badge SVG
  GET  /health              - Health check

Press Ctrl+C to stop
""")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
