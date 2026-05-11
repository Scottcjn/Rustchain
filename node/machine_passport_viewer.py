# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
"""
Machine Passport Web Viewer

Provides web UI routes for viewing machine passports.
Includes vintage computer aesthetic styling.

Issue: #2309
"""

from flask import Blueprint, render_template_string, abort
from machine_passport import MachinePassportLedger
import os

# Create blueprint
passport_viewer_bp = Blueprint('passport_viewer', __name__, url_prefix='/passport')

# Database path
PASSPORT_DB_PATH = os.environ.get('PASSPORT_DB_PATH', 'machine_passports.db')
_ledger = None


def get_ledger():
    global _ledger
    if _ledger is None:
        _ledger = MachinePassportLedger(PASSPORT_DB_PATH)
    return _ledger


# HTML Template with vintage computer aesthetic
PASSPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Machine Passport - {{ passport.name }}</title>
    <style>
        :root {
            --bg-color: #1a1a2e;
            --card-bg: #16213e;
            --accent: #e94560;
            --text-primary: #eee;
            --text-secondary: #a0a0a0;
            --border: #0f3460;
            --crt-scanline: rgba(18, 16, 16, 0.1);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Courier New', monospace;
            background: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%),
                linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 2px, 3px 100%;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            border-bottom: 2px solid var(--accent);
        }
        
        header h1 {
            font-size: 2.5em;
            color: var(--accent);
            text-shadow: 0 0 10px var(--accent);
            margin-bottom: 10px;
        }
        
        header .subtitle {
            color: var(--text-secondary);
            font-size: 1.1em;
        }
        
        .passport-card {
            background: var(--card-bg);
            border: 2px solid var(--border);
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 0 20px rgba(233, 69, 96, 0.2);
        }
        
        .passport-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .machine-name {
            font-size: 2em;
            color: var(--accent);
        }
        
        .machine-id {
            font-size: 0.9em;
            color: var(--text-secondary);
            font-family: monospace;
        }
        
        .details-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .detail-item {
            background: rgba(15, 52, 96, 0.5);
            padding: 15px;
            border-radius: 5px;
            border-left: 3px solid var(--accent);
        }
        
        .detail-label {
            font-size: 0.85em;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        
        .detail-value {
            font-size: 1.1em;
            font-weight: bold;
        }
        
        .section {
            margin-top: 30px;
        }
        
        .section-title {
            font-size: 1.5em;
            color: var(--accent);
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }
        
        .timeline {
            position: relative;
            padding-left: 30px;
        }
        
        .timeline::before {
            content: '';
            position: absolute;
            left: 10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--border);
        }
        
        .timeline-item {
            position: relative;
            margin-bottom: 25px;
            padding: 15px;
            background: rgba(15, 52, 96, 0.3);
            border-radius: 5px;
        }
        
        .timeline-item::before {
            content: '';
            position: absolute;
            left: -24px;
            top: 20px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--accent);
        }
        
        .timeline-date {
            font-size: 0.85em;
            color: var(--text-secondary);
            margin-bottom: 5px;
        }
        
        .timeline-title {
            font-size: 1.1em;
            font-weight: bold;
            color: var(--accent);
            margin-bottom: 10px;
        }
        
        .timeline-content {
            color: var(--text-primary);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .stat-box {
            background: rgba(15, 52, 96, 0.5);
            padding: 20px;
            border-radius: 5px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 2em;
            color: var(--accent);
            font-weight: bold;
        }
        
        .stat-label {
            font-size: 0.85em;
            color: var(--text-secondary);
            margin-top: 5px;
        }
        
        .actions {
            display: flex;
            gap: 15px;
            margin-top: 30px;
            flex-wrap: wrap;
        }
        
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: var(--accent);
            color: white;
            text-decoration: none;
            border-radius: 5px;
            border: none;
            cursor: pointer;
            font-family: inherit;
            font-size: 1em;
            transition: all 0.3s ease;
        }
        
        .btn:hover {
            background: #ff6b6b;
            box-shadow: 0 0 15px var(--accent);
        }
        
        .btn-secondary {
            background: transparent;
            border: 2px solid var(--accent);
        }
        
        .btn-secondary:hover {
            background: var(--accent);
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }
        
        .qr-placeholder {
            text-align: center;
            padding: 20px;
        }
        
        footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            color: var(--text-secondary);
            font-size: 0.85em;
        }
        
        @media (max-width: 768px) {
            .passport-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
            }
            
            header h1 {
                font-size: 1.8em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔧 MACHINE PASSPORT</h1>
            <div class="subtitle">RustChain Relic Registry — Every Machine Has a Story</div>
        </header>
        
        <div class="passport-card">
            <div class="passport-header">
                <div>
                    <div class="machine-name">{{ passport.name }}</div>
                    <div class="machine-id">ID: {{ passport.machine_id }}</div>
                </div>
                {% if passport.architecture %}
                <div style="text-align: right;">
                    <div style="font-size: 1.5em; color: var(--accent);">{{ passport.architecture }}</div>
                    {% if passport.manufacture_year %}
                    <div style="color: var(--text-secondary);">Est. {{ passport.manufacture_year }}</div>
                    {% endif %}
                </div>
                {% endif %}
            </div>
            
            <div class="details-grid">
                <div class="detail-item">
                    <div class="detail-label">Owner</div>
                    <div class="detail-value">{{ passport.owner_miner_id[:20] }}{% if passport.owner_miner_id|length > 20 %}...{% endif %}</div>
                </div>
                
                {% if passport.manufacture_year %}
                <div class="detail-item">
                    <div class="detail-label">Manufacture Year</div>
                    <div class="detail-value">{{ passport.manufacture_year }}</div>
                </div>
                {% endif %}
                
                {% if passport.provenance %}
                <div class="detail-item">
                    <div class="detail-label">Provenance</div>
                    <div class="detail-value">{{ passport.provenance }}</div>
                </div>
                {% endif %}
                
                <div class="detail-item">
                    <div class="detail-label">Created</div>
                    <div class="detail-value">{{ passport.created_at | timestamp_to_date }}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Last Updated</div>
                    <div class="detail-value">{{ passport.updated_at | timestamp_to_date }}</div>
                </div>
            </div>
            
            {% if passport.photo_url %}
            <div style="text-align: center; margin: 30px 0;">
                <img src="{{ passport.photo_url }}" alt="{{ passport.name }}" 
                     style="max-width: 100%; max-height: 400px; border-radius: 10px; border: 2px solid var(--border);">
            </div>
            {% endif %}
            
            <div class="actions">
                <a href="{{ passport_url }}/pdf" class="btn" target="_blank">📄 Download PDF</a>
                <button class="btn btn-secondary" onclick="showQR()">📱 Show QR Code</button>
                <a href="/" class="btn btn-secondary">← Back to List</a>
            </div>
            
            <div id="qr-container" class="qr-placeholder" style="display: none;">
                <div style="margin-top: 20px;">
                    <div style="color: var(--text-secondary); margin-bottom: 10px;">Scan to view this passport</div>
                    <img id="qr-image" src="" alt="QR Code" style="max-width: 200px; border: 5px solid white; border-radius: 5px;">
                </div>
            </div>
        </div>
        
        <!-- Repair History -->
        <div class="passport-card section">
            <div class="section-title">📋 Repair History</div>
            {% if repair_log %}
            <div class="timeline">
                {% for entry in repair_log %}
                <div class="timeline-item">
                    <div class="timeline-date">{{ entry.repair_date | timestamp_to_date }}</div>
                    <div class="timeline-title">{{ entry.repair_type }}</div>
                    <div class="timeline-content">
                        {{ entry.description }}
                        {% if entry.parts_replaced %}
                        <div style="margin-top: 10px; font-size: 0.9em; color: var(--text-secondary);">
                            <strong>Parts:</strong> {{ entry.parts_replaced }}
                        </div>
                        {% endif %}
                        {% if entry.technician %}
                        <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 5px;">
                            <strong>Technician:</strong> {{ entry.technician }}
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">No repair history recorded yet.</div>
            {% endif %}
        </div>
        
        <!-- Attestation History -->
        <div class="passport-card section">
            <div class="section-title">✅ Attestation History</div>
            {% if attestations %}
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-value">{{ total_epochs }}</div>
                    <div class="stat-label">Total Epochs</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{{ total_rtc }}</div>
                    <div class="stat-label">Total RTC Earned</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{{ attestations|length }}</div>
                    <div class="stat-label">Attestations</div>
                </div>
            </div>
            
            <div class="timeline" style="margin-top: 30px;">
                {% for att in attestations[:10] %}
                <div class="timeline-item">
                    <div class="timeline-date">{{ att.attestation_ts | timestamp_to_date }}</div>
                    <div class="timeline-title">
                        {% if att.epoch %}Epoch {{ att.epoch }}{% else %}Attestation{% endif %}
                    </div>
                    <div class="timeline-content">
                        {% if att.entropy_score %}
                        <div>Entropy Score: {{ att.entropy_score }}</div>
                        {% endif %}
                        {% if att.hardware_binding %}
                        <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 5px;">
                            Hardware Binding: {{ att.hardware_binding[:30] }}...
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">No attestation history yet.</div>
            {% endif %}
        </div>
        
        <!-- Benchmark Signatures -->
        <div class="passport-card section">
            <div class="section-title">⚡ Benchmark Signatures</div>
            {% if benchmarks %}
            <div class="timeline">
                {% for bench in benchmarks[:10] %}
                <div class="timeline-item">
                    <div class="timeline-date">{{ bench.benchmark_ts | timestamp_to_date }}</div>
                    <div class="timeline-title">Performance Profile</div>
                    <div class="timeline-content">
                        {% if bench.compute_score %}
                        <div>Compute Score: {{ bench.compute_score }}</div>
                        {% endif %}
                        {% if bench.memory_bandwidth %}
                        <div>Memory Bandwidth: {{ bench.memory_bandwidth }} MB/s</div>
                        {% endif %}
                        {% if bench.simd_identity %}
                        <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 5px;">
                            SIMD: {{ bench.simd_identity }}
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">No benchmark signatures recorded.</div>
            {% endif %}
        </div>
        
        <!-- Lineage Notes -->
        <div class="passport-card section">
            <div class="section-title">📜 Lineage Notes</div>
            {% if lineage %}
            <div class="timeline">
                {% for note in lineage %}
                <div class="timeline-item">
                    <div class="timeline-date">{{ note.lineage_ts | timestamp_to_date }}</div>
                    <div class="timeline-title">{{ note.event_type | capitalize }}</div>
                    <div class="timeline-content">
                        {{ note.description or 'Ownership event recorded' }}
                        {% if note.from_owner and note.to_owner %}
                        <div style="margin-top: 10px; font-size: 0.9em; color: var(--text-secondary);">
                            <strong>Transfer:</strong> {{ note.from_owner[:15] }}... → {{ note.to_owner[:15] }}...
                        </div>
                        {% endif %}
                        {% if note.tx_hash %}
                        <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 5px;">
                            <strong>TX:</strong> {{ note.tx_hash[:20] }}...
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">No lineage notes recorded.</div>
            {% endif %}
        </div>
        
        <footer>
            <div>RustChain Machine Passport • Issue #2309 • Give Every Relic a Biography</div>
            <div style="margin-top: 10px;">Generated: {{ generated_at | timestamp_to_date }}</div>
        </footer>
    </div>
    
    <script>
        async function showQR() {
            const container = document.getElementById('qr-container');
            const img = document.getElementById('qr-image');
            
            if (container.style.display === 'block') {
                container.style.display = 'none';
                return;
            }
            
            try {
                const response = await fetch('/api/machine-passport/{{ passport.machine_id }}/qr');
                const data = await response.json();
                
                if (data.ok && data.qr_code) {
                    img.src = data.qr_code;
                    container.style.display = 'block';
                }
            } catch (error) {
                console.error('Failed to load QR code:', error);
            }
        }
    </script>
</body>
</html>
"""


def timestamp_to_date(ts):
    """Convert Unix timestamp to readable date."""
    from datetime import datetime
    if not ts:
        return 'N/A'
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


@passport_viewer_bp.route('/<machine_id>')
def view_passport(machine_id: str):
    """View a machine passport."""
    ledger = get_ledger()
    
    passport = ledger.get_passport(machine_id)
    if not passport:
        abort(404)
    
    # Get all related data
    repair_log = ledger.get_repair_log(machine_id)
    attestations = ledger.get_attestation_history(machine_id)
    benchmarks = ledger.get_benchmark_signatures(machine_id)
    lineage = ledger.get_lineage_notes(machine_id)
    
    # Calculate summary stats
    total_epochs = max((a.get('total_epochs', 0) for a in attestations), default=0)
    total_rtc = max((a.get('total_rtc_earned', 0) for a in attestations), default=0)
    total_rtc_formatted = f"{total_rtc / 1_000_000:.2f}" if total_rtc else "0"
    
    # Render template
    from jinja2 import Template
    template = Template(PASSPORT_TEMPLATE)
    
    # Add custom filters
    template.environment.filters['timestamp_to_date'] = timestamp_to_date
    
    html = template.render(
        passport=passport,
        repair_log=repair_log,
        attestations=attestations,
        benchmarks=benchmarks,
        lineage=lineage,
        total_epochs=total_epochs,
        total_rtc=total_rtc_formatted,
        passport_url=f"/passport/{machine_id}",
        generated_at=int(__import__('time').time()),
    )
    
    return html


@passport_viewer_bp.route('/')
def list_passports():
    """List all machine passports."""
    from flask import request, jsonify
    
    ledger = get_ledger()
    
    # Get query parameters
    owner = request.args.get('owner')
    architecture = request.args.get('architecture')
    try:
        limit_raw = request.args.get('limit', '100')
        limit = int(limit_raw)
        if limit < 1:
            return jsonify({"error": "limit must be >= 1"}), 400
        limit = min(limit, 500)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid limit parameter: must be an integer"}), 400
    
    passports = ledger.list_passports(
        owner_miner_id=owner,
        architecture=architecture,
        limit=limit,
    )
    
    # Simple HTML list view
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Machine Passports - RustChain</title>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                background: #1a1a2e;
                color: #eee;
                padding: 20px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ color: #e94560; }}
            .passport-list {{ list-style: none; }}
            .passport-item {{
                background: #16213e;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 20px;
                margin: 15px 0;
            }}
            .passport-item a {{
                color: #e94560;
                text-decoration: none;
                font-size: 1.3em;
            }}
            .passport-item a:hover {{ text-decoration: underline; }}
            .meta {{ color: #a0a0a0; font-size: 0.9em; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Machine Passports</h1>
            <p style="color: #a0a0a0;">{len(passports)} passport(s) found</p>
            
            <ul class="passport-list">
                {''.join(f'''
                <li class="passport-item">
                    <a href="/passport/{p.machine_id}">{p.name}</a>
                    <div class="meta">
                        ID: {p.machine_id[:16]}... | 
                        Owner: {p.owner_miner_id[:15]}... | 
                        Architecture: {p.architecture or 'Unknown'} |
                        Created: {timestamp_to_date(p.created_at)}
                    </div>
                </li>
                ''' for p in passports)}
            </ul>
            
            <p style="margin-top: 30px; color: #a0a0a0;">
                <a href="/" style="color: #e94560;">← Back to Home</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    return html


def register_passport_viewer_routes(app):
    """Register passport viewer routes with a Flask app."""
    app.register_blueprint(passport_viewer_bp)
    print("[Machine Passport] Web viewer routes registered")
