"""
Hall of Rust - Immortal Registry for Dying Hardware
====================================================
Every machine that ever attests gets a permanent on-chain memorial.
This is the emotional core of RustChain.
"""

from flask import Blueprint, jsonify, request
import sqlite3
import hashlib
import hmac
import os
import time
import json

hall_bp = Blueprint('hall_of_rust', __name__)

# Rust Score calculation weights
RUST_WEIGHTS = {
    'age_years': 10,           # Points per year of hardware age
    'attestation_count': 0.1,  # Points per attestation
    'uptime_hours': 0.01,      # Points per hour of total uptime
    'thermal_events': 5,       # Points per thermal anomaly (badge of honor)
    'capacitor_plague': 100,   # Bonus for 2001-2006 bad cap era
    'first_attestation': 50,   # Bonus for being among first 100 miners
}

# Capacitor plague era models (infamous bad electrolytic caps)
CAPACITOR_PLAGUE_MODELS = [
    'PowerMac3,',      # G4 Quicksilver/MDD 2001-2003
    'PowerMac7,2',     # G5 early models
    'PowerMac7,3',     # G5
    'iMac,1',          # iMac G4
    'PowerBook5,',     # PowerBook G4 aluminum
    'Dell GX260',      # Dell Optiplex plague
    'Dell GX270',
    'Dell GX280',
]

def current_utc_year():
    """Return the current UTC year for hardware age calculations."""
    return time.gmtime().tm_year

def init_hall_tables(db_path):
    """Create Hall of Rust tables if they don't exist."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Main Hall of Rust registry
    c.execute('''
        CREATE TABLE IF NOT EXISTS hall_of_rust (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint_hash TEXT UNIQUE NOT NULL,
            miner_id TEXT NOT NULL,
            device_family TEXT,
            device_arch TEXT,
            device_model TEXT,
            manufacture_year INTEGER,
            first_attestation INTEGER NOT NULL,
            last_attestation INTEGER,
            total_attestations INTEGER DEFAULT 1,
            total_rtc_earned REAL DEFAULT 0,
            rust_score REAL DEFAULT 0,
            nickname TEXT,
            eulogy TEXT,
            photo_hash TEXT,
            is_deceased INTEGER DEFAULT 0,
            deceased_at INTEGER,
            capacitor_plague INTEGER DEFAULT 0,
            thermal_events INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        )
    ''')
    
    # Rust Score history for leaderboard
    c.execute('''
        CREATE TABLE IF NOT EXISTS rust_score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint_hash TEXT NOT NULL,
            rust_score REAL NOT NULL,
            calculated_at INTEGER NOT NULL,
            FOREIGN KEY (fingerprint_hash) REFERENCES hall_of_rust(fingerprint_hash)
        )
    ''')
    
    conn.commit()
    conn.close()

def calculate_rust_score(machine):
    """Calculate the Rust Score for a machine - higher = rustier = better."""
    score = 0
    
    # Age bonus (estimated from model/arch)
    if machine.get('manufacture_year'):
        age = max(0, current_utc_year() - int(machine['manufacture_year']))
        score += age * RUST_WEIGHTS['age_years']
    
    # Attestation loyalty
    score += machine.get('total_attestations', 0) * RUST_WEIGHTS['attestation_count']
    
    # Capacitor plague era bonus
    model = machine.get('device_model', '')
    for plague_model in CAPACITOR_PLAGUE_MODELS:
        if plague_model in model:
            score += RUST_WEIGHTS['capacitor_plague']
            break
    
    # Thermal events (more = rustier)
    score += machine.get('thermal_events', 0) * RUST_WEIGHTS['thermal_events']
    
    # Early adopter bonus
    if machine.get('id', 999) <= 100:
        score += RUST_WEIGHTS['first_attestation']
    
    # Architecture bonuses
    arch_bonus = {
        'G3': 80, 'G4': 70, 'G5': 60,
        '486': 150, 'pentium': 100, 'pentium4': 50,
        'retro': 40, 'apple_silicon': 5, 'modern': 0
    }
    arch = machine.get('device_arch', 'modern').lower()
    for key, bonus in arch_bonus.items():
        if key in arch:
            score += bonus
            break
    
    return round(score, 2)

def estimate_manufacture_year(model, arch):
    """Estimate manufacture year from model string."""
    year_hints = {
        'PowerMac1,': 1999, 'PowerMac3,1': 2000, 'PowerMac3,3': 2001,
        'PowerMac3,4': 2002, 'PowerMac3,5': 2002, 'PowerMac3,6': 2003,
        'PowerMac7,2': 2003, 'PowerMac7,3': 2004, 'PowerMac11,2': 2005,
        'PowerBook5,': 2003, 'PowerBook6,': 2004,
        'iMac4,': 2006, 'iMac5,': 2006,
        'MacPro1,': 2006, 'MacPro3,': 2008,
    }
    for hint, year in year_hints.items():
        if hint in model:
            return year
    
    # Fallback by architecture
    arch_years = {'G3': 1998, 'G4': 2001, 'G5': 2004, '486': 1992, 'pentium': 1996}
    for key, year in arch_years.items():
        if key.lower() in arch.lower():
            return year
    return 2020  # Modern default


def _require_hall_admin():
    expected = os.environ.get("RC_ADMIN_KEY", "").strip()
    if not expected:
        return jsonify({'ok': False, 'error': 'RC_ADMIN_KEY not configured'}), 503

    provided = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    expected_bytes = expected.encode("utf-8")
    provided_bytes = provided.encode("utf-8") if provided else b""
    if not provided_bytes or not hmac.compare_digest(provided_bytes, expected_bytes):
        return jsonify({
            'ok': False,
            'error': 'unauthorized',
            'message': 'Admin key required',
        }), 401

    return None

# ============== API ENDPOINTS ==============

@hall_bp.route('/hall/induct', methods=['POST'])
def induct_machine():
    """Automatically induct a machine into the Hall of Rust on first attestation."""
    data = request.json or {}
    
    # Generate fingerprint hash from hardware identifiers
    # SECURITY FIX: Fingerprint based on HARDWARE ONLY (not wallet ID)
    # This prevents multiple wallets on same machine from getting multiple Hall entries
    hw_serial = data.get('cpu_serial', data.get('hardware_id', 'unknown'))
    fp_data = f"{data.get('device_model', '')}{data.get('device_arch', '')}{hw_serial}"
    fingerprint_hash = hashlib.sha256(fp_data.encode()).hexdigest()[:32]
    
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Check if already inducted
        c.execute("SELECT id, total_attestations FROM hall_of_rust WHERE fingerprint_hash = ?", 
                  (fingerprint_hash,))
        existing = c.fetchone()
        
        now = int(time.time())
        model = data.get('device_model', 'Unknown')
        arch = data.get('device_arch', 'modern')
        
        if existing:
            # Update attestation count
            c.execute("""
                UPDATE hall_of_rust 
                SET total_attestations = total_attestations + 1,
                    last_attestation = ?
                WHERE fingerprint_hash = ?
            """, (now, fingerprint_hash))
            conn.commit()
            conn.close()
            return jsonify({
                'inducted': False, 
                'message': 'Already in Hall of Rust',
                'attestation_count': existing[1] + 1
            })
        
        # New induction!
        mfg_year = estimate_manufacture_year(model, arch)
        is_plague = any(pm in model for pm in CAPACITOR_PLAGUE_MODELS)
        
        c.execute("""
            INSERT INTO hall_of_rust 
            (fingerprint_hash, miner_id, device_family, device_arch, device_model,
             manufacture_year, first_attestation, last_attestation, capacitor_plague, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fingerprint_hash,
            data.get('miner_id', 'anonymous'),
            data.get('device_family', 'Unknown'),
            arch,
            model,
            mfg_year,
            now, now,
            1 if is_plague else 0,
            now
        ))
        
        # Calculate initial Rust Score
        machine = {
            'manufacture_year': mfg_year,
            'device_arch': arch,
            'device_model': model,
            'total_attestations': 1,
            'capacitor_plague': is_plague,
            'id': c.lastrowid
        }
        rust_score = calculate_rust_score(machine)
        
        c.execute("UPDATE hall_of_rust SET rust_score = ? WHERE fingerprint_hash = ?",
                  (rust_score, fingerprint_hash))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'inducted': True,
            'message': 'Welcome to the Hall of Rust!',
            'fingerprint': fingerprint_hash,
            'rust_score': rust_score,
            'manufacture_year': mfg_year,
            'capacitor_plague': is_plague
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@hall_bp.route('/hall/machine/<fingerprint>', methods=['GET'])
def get_machine(fingerprint):
    """Get a machine's Hall of Rust entry."""
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM hall_of_rust WHERE fingerprint_hash = ?", (fingerprint,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Machine not found in Hall of Rust'}), 404
        
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@hall_bp.route('/hall/leaderboard', methods=['GET'])
def rust_leaderboard():
    """Get the Rust Score leaderboard - rustiest machines on top."""
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        limit = request.args.get('limit', 50, type=int)
        
        c.execute("""
            SELECT fingerprint_hash, miner_id, device_arch, device_model,
                   manufacture_year, rust_score, total_attestations,
                   total_rtc_earned, capacitor_plague, is_deceased, nickname
            FROM hall_of_rust 
            ORDER BY rust_score DESC 
            LIMIT ?
        """, (limit,))
        
        rows = c.fetchall()
        conn.close()
        
        leaderboard = []
        for i, row in enumerate(rows, 1):
            entry = dict(row)
            entry['rank'] = i
            entry['badge'] = get_rust_badge(entry['rust_score'])
            leaderboard.append(entry)
        
        return jsonify({
            'leaderboard': leaderboard,
            'total_machines': len(leaderboard),
            'generated_at': int(time.time())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@hall_bp.route('/hall/eulogy/<fingerprint>', methods=['POST'])
def set_eulogy(fingerprint):
    """Set a eulogy/nickname for a machine. For when it finally dies."""
    auth_error = _require_hall_admin()
    if auth_error:
        return auth_error

    data = request.json or {}
    
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        updates = []
        params = []
        
        if 'nickname' in data:
            updates.append('nickname = ?')
            params.append(data['nickname'][:64])
        
        if 'eulogy' in data:
            updates.append('eulogy = ?')
            params.append(data['eulogy'][:500])
        
        if 'is_deceased' in data and data['is_deceased']:
            updates.append('is_deceased = 1')
            updates.append('deceased_at = ?')
            params.append(int(time.time()))
        
        if updates:
            params.append(fingerprint)
            c.execute(f"UPDATE hall_of_rust SET {', '.join(updates)} WHERE fingerprint_hash = ?", params)
            conn.commit()
        
        conn.close()
        return jsonify({'ok': True, 'message': 'Memorial updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@hall_bp.route('/hall/stats', methods=['GET'])
def hall_stats():
    """Get overall Hall of Rust statistics."""
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        stats = {}
        
        c.execute("""SELECT COUNT(*) FROM hall_of_rust WHERE device_arch NOT IN ('unknown', 'default')""")
        stats['total_machines'] = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM hall_of_rust WHERE is_deceased = 1")
        stats['deceased_machines'] = c.fetchone()[0]
        
        c.execute("""SELECT SUM(total_attestations) FROM hall_of_rust WHERE device_arch NOT IN ('unknown', 'default')""")
        stats['total_attestations'] = c.fetchone()[0] or 0
        
        c.execute("""SELECT AVG(rust_score) FROM hall_of_rust WHERE device_arch NOT IN ('unknown', 'default')""")
        stats['average_rust_score'] = round(c.fetchone()[0] or 0, 2)
        
        c.execute("SELECT MAX(rust_score) FROM hall_of_rust")
        stats['highest_rust_score'] = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM hall_of_rust WHERE capacitor_plague = 1")
        stats['capacitor_plague_survivors'] = c.fetchone()[0]
        
        # Oldest machine
        c.execute("SELECT miner_id, manufacture_year FROM hall_of_rust ORDER BY manufacture_year ASC LIMIT 1")
        oldest = c.fetchone()
        if oldest:
            stats['oldest_machine'] = {'miner_id': oldest[0], 'year': oldest[1]}
        
        conn.close()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_rust_badge(score):
    """Get a badge based on Rust Score."""
    if score >= 200:
        return "Oxidized Legend"
    elif score >= 150:
        return "Tetanus Master"
    elif score >= 100:
        return "Patina Veteran"
    elif score >= 70:
        return "Rust Warrior"
    elif score >= 50:
        return "Corroded Knight"
    elif score >= 30:
        return "Tarnished Squire"
    else:
        return "Fresh Metal"

def get_ascii_silhouette(device_arch, device_model=""):
    """Return an ASCII silhouette for known machine families."""
    arch = str(device_arch or "").lower()
    model = str(device_model or "").lower()

    if any(k in arch for k in ("g4", "g5", "powerpc")) or "powermac" in model:
        return (
            "      __________\n"
            "     / ________ \\\n"
            "    / / ______ \\ \\\n"
            "   | | |  __  | | |\n"
            "   | | | |  | | | |\n"
            "   | | | |__| | | |\n"
            "   | | |______| | |\n"
            "   | |  ______  | |\n"
            "   | | |      | | |\n"
            "   |_|_|______|_|_|\n"
        )
    if any(k in arch for k in ("486", "pentium", "x86")):
        return (
            "   __________________\n"
            "  /_________________/|\n"
            "  |  ___      ___  | |\n"
            "  | |___|    |___| | |\n"
            "  |   _________    | |\n"
            "  |  |  FLOPPY |   | |\n"
            "  |  |_________|   | |\n"
            "  |_______________ |/\n"
        )
    return (
        "    _____________\n"
        "   / ___________ \\\n"
        "  | |  MACHINE  | |\n"
        "  | |___________| |\n"
        "  |  ___________  |\n"
        "  | |           | |\n"
        "  |_|___________|_|\n"
    )

def _table_exists(cursor, table_name):
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None

@hall_bp.route('/api/hall_of_fame/machine', methods=['GET'])
def api_hall_of_fame_machine():
    """Machine profile endpoint for Hall of Fame detail page."""
    machine_id = (request.args.get('id') or '').strip()
    if not machine_id:
        return jsonify({'error': 'missing id'}), 400

    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        now = int(time.time())

        c.execute("SELECT * FROM hall_of_rust WHERE fingerprint_hash = ?", (machine_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'machine not found'}), 404

        machine = dict(row)
        machine['badge'] = get_rust_badge(float(machine.get('rust_score') or 0))
        machine['ascii_silhouette'] = get_ascii_silhouette(
            machine.get('device_arch'),
            machine.get('device_model'),
        )
        mfg = machine.get('manufacture_year')
        current_year = time.gmtime(now).tm_year
        machine['age_years'] = max(0, current_year - int(mfg)) if mfg else None

        # Last 30 days timeline from attestation history (best-effort).
        start_ts = now - 30 * 86400
        miner_pk = machine.get('miner_id') or ''
        timeline = []
        if miner_pk and _table_exists(c, 'miner_attest_history'):
            c.execute(
                """
                SELECT date(ts_ok, 'unixepoch') AS day,
                       COUNT(*) AS attestations
                FROM miner_attest_history
                WHERE miner = ? AND ts_ok >= ?
                GROUP BY day
                ORDER BY day ASC
                """,
                (miner_pk, start_ts),
            )
            timeline = [
                {
                    'date': r['day'],
                    'attestations': int(r['attestations'] or 0),
                    'rust_score': machine.get('rust_score'),
                    'samples': int(r['attestations'] or 0),
                }
                for r in c.fetchall()
            ]
        elif _table_exists(c, 'rust_score_history'):
            c.execute(
                """
                SELECT date(calculated_at, 'unixepoch') AS day,
                       MAX(rust_score) AS rust_score,
                       COUNT(*) AS samples
                FROM rust_score_history
                WHERE fingerprint_hash = ? AND calculated_at >= ?
                GROUP BY day
                ORDER BY day ASC
                """,
                (machine_id, start_ts),
            )
            timeline = [
                {
                    'date': r['day'],
                    'rust_score': r['rust_score'],
                    'samples': int(r['samples'] or 0),
                    'attestations': int(r['samples'] or 0),
                }
                for r in c.fetchall()
            ]

        # Reward participation (best-effort) from enrollments + pending ledger credits.
        enrolled_epochs = 0
        reward_count = 0
        reward_sum_i64 = 0
        if miner_pk and _table_exists(c, 'epoch_enroll'):
            try:
                c.execute("SELECT COUNT(*) AS n FROM epoch_enroll WHERE miner_pk = ?", (miner_pk,))
                enrolled_epochs = int((c.fetchone() or {'n': 0})['n'] or 0)
            except Exception:
                enrolled_epochs = 0

        if miner_pk and _table_exists(c, 'pending_ledger'):
            try:
                c.execute(
                    """
                    SELECT COUNT(*) AS n, COALESCE(SUM(amount_i64),0) AS s
                    FROM pending_ledger
                    WHERE to_miner = ? AND status = 'confirmed'
                    """,
                    (miner_pk,),
                )
                ledger_row = c.fetchone()
                reward_count = int((ledger_row or {'n': 0})['n'] or 0)
                reward_sum_i64 = int((ledger_row or {'s': 0})['s'] or 0)
            except Exception:
                reward_count = 0
                reward_sum_i64 = 0

        reward_participation = {
            'enrolled_epochs': int(enrolled_epochs),
            'confirmed_reward_events': int(reward_count or 0),
            'confirmed_reward_rtc': round((reward_sum_i64 or 0) / 1_000_000.0, 6),
        }

        conn.close()
        return jsonify({
            'machine': machine,
            'attestation_timeline_30d': timeline,
            'reward_participation': reward_participation,
            'generated_at': now,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def register_hall_endpoints(app, db_path):
    """Register Hall of Rust endpoints with Flask app."""
    app.config['DB_PATH'] = db_path
    init_hall_tables(db_path)
    app.register_blueprint(hall_bp)
    print("[HALL OF RUST] Endpoints registered - The machines will be remembered!")

# ============== ENHANCED STATS ==============

import random

# Fun facts about vintage hardware
VINTAGE_FACTS = [
    "The PowerPC G4 was so powerful, the US classified it as a 'weapon' under export restrictions.",
    "A 2001 G4 has been running continuously for 24 years - that's 8,760 days of uptime potential.",
    "The G5 was the first 64-bit desktop processor, beating Intel to market by years.",
    "PowerPC chips ran the original Xbox 360, PlayStation 3, and Nintendo Wii.",
    "A G4 can hash attestations while consuming less than 50 watts.",
    "The 'G' in G4 stood for 'Generation' - the 4th gen of PowerPC.",
    "Some G4s are still running Mac OS 9 - an OS from 1999.",
    "The PowerBook G4 Titanium was nicknamed 'TiBook' by fans.",
    "Apple's transition from PowerPC to Intel took only 2 years (2005-2007).",
    "The iMac G4's swivel LCD earned it the nickname 'sunflower'.",
    "Retro x86 machines often outlast modern hardware due to simpler components.",
    "The capacitor plague of 2001-2006 killed millions of motherboards.",
    "Some 486 processors from 1989 are still running today.",
]

@hall_bp.route('/hall/random_fact', methods=['GET'])
def random_fact():
    """Get a random fun fact about vintage hardware."""
    return jsonify({
        'fact': random.choice(VINTAGE_FACTS),
        'generated_at': int(time.time())
    })

@hall_bp.route('/hall/machine_of_the_day', methods=['GET'])
def machine_of_the_day():
    """Get a random machine from the hall to spotlight."""
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get a random machine with some rust
        c.execute("""
            SELECT * FROM hall_of_rust 
            WHERE device_arch NOT IN ('unknown', 'default')
            AND rust_score > 100
            ORDER BY RANDOM() 
            LIMIT 1
        """)
        row = c.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'No worthy machines found'}), 404
        
        machine = dict(row)
        machine['badge'] = get_rust_badge(machine['rust_score'])
        machine['fun_fact'] = random.choice(VINTAGE_FACTS)
        mfg = machine.get('manufacture_year')
        machine['age_years'] = max(0, current_utc_year() - int(mfg)) if mfg else None
        
        return jsonify(machine)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@hall_bp.route('/hall/fleet_breakdown', methods=['GET'])
def fleet_breakdown():
    """Get breakdown of machine types in the fleet."""
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT device_arch, 
                   COUNT(*) as count, 
                   MIN(manufacture_year) as oldest_year,
                   MAX(rust_score) as top_score,
                   AVG(rust_score) as avg_score
            FROM hall_of_rust 
            WHERE device_arch NOT IN ('unknown', 'default')
            GROUP BY device_arch 
            ORDER BY count DESC
        """)
        
        breakdown = []
        for row in c.fetchall():
            breakdown.append({
                'architecture': row[0],
                'count': row[1],
                'oldest_year': row[2],
                'top_rust_score': row[3],
                'avg_rust_score': round(row[4], 1)
            })
        
        conn.close()
        return jsonify({
            'breakdown': breakdown,
            'total_architectures': len(breakdown),
            'generated_at': int(time.time())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@hall_bp.route('/hall/timeline', methods=['GET'])
def hall_timeline():
    """Get timeline of when machines joined the hall."""
    try:
        from flask import current_app
        db_path = current_app.config.get('DB_PATH', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT date(first_attestation, 'unixepoch') as join_date,
                   COUNT(*) as machines_joined,
                   GROUP_CONCAT(device_arch) as architectures
            FROM hall_of_rust 
            WHERE device_arch NOT IN ('unknown', 'default')
            GROUP BY join_date
            ORDER BY join_date DESC
            LIMIT 30
        """)
        
        timeline = []
        for row in c.fetchall():
            timeline.append({
                'date': row[0],
                'machines_joined': row[1],
                'architectures': row[2].split(',') if row[2] else []
            })
        
        conn.close()
        return jsonify({
            'timeline': timeline,
            'generated_at': int(time.time())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
