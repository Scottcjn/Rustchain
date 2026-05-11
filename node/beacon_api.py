#!/usr/bin/env python3
"""
Beacon Atlas API - Flask routes for 3D visualization backend
Provides endpoints for agents, contracts, bounties, reputation, and chat.
"""
import json
import os
import time
import hashlib
import sqlite3
from datetime import datetime
from flask import Blueprint, jsonify, request, g

beacon_api = Blueprint('beacon_api', __name__)

DB_PATH = 'rustchain_v2.db'

# In-memory cache for bounties (synced from GitHub)
bounty_cache = {
    'data': [],
    'timestamp': 0,
    'ttl': 300  # 5 minutes
}

# Contract store (persistent in DB)
contract_store = []

# Chat session store
chat_sessions = {}


def get_db():
    """Get database connection for current request context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@beacon_api.teardown_request
def close_db(exception):
    """Close database connection at end of request."""
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


def init_beacon_tables(db_path=DB_PATH):
    """Initialize Beacon Atlas database tables."""
    with sqlite3.connect(db_path) as conn:
        # Contracts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beacon_contracts (
                id TEXT PRIMARY KEY,
                from_agent TEXT NOT NULL,
                to_agent TEXT,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'RTC',
                term TEXT NOT NULL,
                state TEXT DEFAULT 'offered',
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            )
        """)
        
        # Bounties table (synced from GitHub)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beacon_bounties (
                id TEXT PRIMARY KEY,
                github_number INTEGER,
                title TEXT NOT NULL,
                reward_rtc REAL,
                reward_text TEXT,
                difficulty TEXT DEFAULT 'ANY',
                github_repo TEXT,
                github_url TEXT,
                state TEXT DEFAULT 'open',
                claimant_agent TEXT,
                completed_by TEXT,
                description TEXT,
                labels TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
        
        # Reputation table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beacon_reputation (
                agent_id TEXT PRIMARY KEY,
                score INTEGER DEFAULT 0,
                bounties_completed INTEGER DEFAULT 0,
                contracts_completed INTEGER DEFAULT 0,
                contracts_breached INTEGER DEFAULT 0,
                total_rtc_earned REAL DEFAULT 0,
                last_updated INTEGER
            )
        """)
        
        # Chat messages table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beacon_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                user_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

        # Relay agents table (for beacon join routing)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relay_agents (
                agent_id TEXT PRIMARY KEY,
                pubkey_hex TEXT NOT NULL,
                name TEXT,
                status TEXT DEFAULT 'active',
                coinbase_address TEXT DEFAULT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contracts_from ON beacon_contracts(from_agent)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contracts_to ON beacon_contracts(to_agent)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contracts_state ON beacon_contracts(state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bounties_state ON beacon_bounties(state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_agent ON beacon_chat(agent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relay_agents_status ON relay_agents(status)")

        conn.commit()


# ============================================================
# AGENTS ENDPOINTS
# ============================================================

@beacon_api.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all registered agents."""
    try:
        db = get_db()
        rows = db.execute(
            "SELECT agent_id, pubkey_hex, name, status, created_at, updated_at FROM relay_agents ORDER BY created_at DESC"
        ).fetchall()

        agents = []
        for row in rows:
            agents.append({
                'agent_id': row['agent_id'],
                'pubkey_hex': row['pubkey_hex'],
                'name': row['name'],
                'status': row['status'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            })

        return jsonify(agents)
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/api/agent/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get single agent details."""
    try:
        db = get_db()
        row = db.execute(
            "SELECT agent_id, pubkey_hex, name, status, coinbase_address, created_at, updated_at FROM relay_agents WHERE agent_id = ?",
            (agent_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Agent not found'}), 404

        return jsonify({
            'agent_id': row['agent_id'],
            'pubkey_hex': row['pubkey_hex'],
            'name': row['name'],
            'status': row['status'],
            'coinbase_address': row['coinbase_address'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        })
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


# ============================================================
# BEACON JOIN ROUTING ENDPOINTS (Issue #2127)
# ============================================================

@beacon_api.route('/beacon/join', methods=['POST', 'OPTIONS'])
def beacon_join():
    """
    Register or update a relay agent in the beacon atlas.
    
    Accepts JSON with:
        - agent_id: Unique agent identifier (required)
        - pubkey_hex: Hex-encoded public key (required, must be valid hex)
        - name: Optional human-readable name
        - coinbase_address: Optional Base network address for payments
    
    Returns:
        - 200: Agent registered/updated successfully
        - 400: Invalid input (missing fields, invalid pubkey_hex format)
    
    Upsert behavior: Duplicate agent_id updates existing record.
    """
    if request.method == 'OPTIONS':
        resp = jsonify({'ok': True})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        return resp

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400

        # Validate required fields
        agent_id = data.get('agent_id')
        pubkey_hex = data.get('pubkey_hex')

        if not agent_id:
            return jsonify({'error': 'Missing required field: agent_id'}), 400
        if not pubkey_hex:
            return jsonify({'error': 'Missing required field: pubkey_hex'}), 400

        # Validate pubkey_hex format (must be valid hex string, optionally with 0x prefix)
        pubkey_clean = pubkey_hex.strip()
        if pubkey_clean.startswith('0x') or pubkey_clean.startswith('0X'):
            pubkey_clean = pubkey_clean[2:]
        
        if not pubkey_clean:
            return jsonify({'error': 'Invalid pubkey_hex: empty after prefix removal'}), 400
        
        try:
            # Validate it's proper hex
            bytes.fromhex(pubkey_clean)
        except ValueError:
            return jsonify({'error': 'Invalid pubkey_hex: must be valid hexadecimal string'}), 400

        # Optional fields
        name = data.get('name')
        coinbase_address = data.get('coinbase_address')
        
        # Validate coinbase_address if provided (should be 0x-prefixed, 40 hex chars)
        if coinbase_address:
            cb_clean = coinbase_address.strip()
            if not (cb_clean.startswith('0x') or cb_clean.startswith('0X')):
                return jsonify({'error': 'Invalid coinbase_address: must start with 0x'}), 400
            cb_hex = cb_clean[2:]
            if len(cb_hex) != 40:
                return jsonify({'error': 'Invalid coinbase_address: must be 20 bytes (40 hex chars)'}), 400
            try:
                bytes.fromhex(cb_hex)
            except ValueError:
                return jsonify({'error': 'Invalid coinbase_address: must be valid hexadecimal'}), 400

        now = int(time.time())

        # Check if agent already exists
        db = get_db()
        existing = db.execute(
            "SELECT pubkey_hex FROM relay_agents WHERE agent_id = ?",
            (agent_id,)
        ).fetchone()

        if existing:
            # Agent exists — NEVER allow pubkey_hex overwrite.
            # Allowing unauthenticated pubkey changes is a full identity
            # takeover: attacker sends join with victim's agent_id and
            # their own public key, hijacking the agent.
            if pubkey_hex != existing['pubkey_hex']:
                return jsonify({
                    'error': 'Cannot change pubkey_hex for existing agent — '
                             'public key is immutable after registration'
                }), 403

            # Update mutable fields only
            db.execute("""
                UPDATE relay_agents
                SET name = COALESCE(?, name),
                    coinbase_address = COALESCE(?, coinbase_address),
                    status = 'active',
                    updated_at = ?
                WHERE agent_id = ?
            """, (name, coinbase_address, now, agent_id))
        else:
            # New agent — insert with pubkey_hex
            db.execute("""
                INSERT INTO relay_agents (agent_id, pubkey_hex, name, status, coinbase_address, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?, ?)
            """, (agent_id, pubkey_hex, name, coinbase_address, now, now))

        db.commit()

        return jsonify({
            'ok': True,
            'agent_id': agent_id,
            'pubkey_hex': pubkey_hex,
            'name': name,
            'status': 'active',
            'timestamp': now,
        })

    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/beacon/atlas', methods=['GET', 'OPTIONS'])
def beacon_atlas():
    """
    Get list of all registered relay agents in the beacon atlas.
    
    Returns array of agent objects with:
        - agent_id: Unique identifier
        - pubkey_hex: Public key (hex)
        - name: Human-readable name (if set)
        - status: Agent status (active, inactive, etc.)
        - created_at: Registration timestamp
        - updated_at: Last update timestamp
    
    Query params:
        - status: Optional filter by status (e.g., ?status=active)
    """
    if request.method == 'OPTIONS':
        resp = jsonify({'ok': True})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        return resp

    try:
        db = get_db()
        
        # Optional status filter
        status_filter = request.args.get('status')
        
        if status_filter:
            rows = db.execute(
                """SELECT agent_id, pubkey_hex, name, status, coinbase_address, created_at, updated_at 
                   FROM relay_agents 
                   WHERE status = ? 
                   ORDER BY created_at DESC""",
                (status_filter,)
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT agent_id, pubkey_hex, name, status, coinbase_address, created_at, updated_at 
                   FROM relay_agents 
                   ORDER BY created_at DESC"""
            ).fetchall()

        agents = []
        for row in rows:
            agents.append({
                'agent_id': row['agent_id'],
                'pubkey_hex': row['pubkey_hex'],
                'name': row['name'],
                'status': row['status'],
                'coinbase_address': row['coinbase_address'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            })

        return jsonify({
            'agents': agents,
            'total': len(agents),
            'timestamp': int(time.time()),
        })

    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


# ============================================================
# CONTRACTS ENDPOINTS
# ============================================================

@beacon_api.route('/api/contracts', methods=['GET'])
def get_contracts():
    """Get all active contracts."""
    try:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM beacon_contracts ORDER BY created_at DESC"
        ).fetchall()
        
        contracts = []
        for row in rows:
            contracts.append({
                'id': row['id'],
                'from': row['from_agent'],
                'to': row['to_agent'],
                'type': row['type'],
                'amount': row['amount'],
                'currency': row['currency'],
                'term': row['term'],
                'state': row['state'],
                'created_at': row['created_at'],
            })
        
        return jsonify(contracts)
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/api/contracts', methods=['POST'])
def create_contract():
    """Create a new contract between agents.
    
    Requires X-Agent-Key header to authenticate the contract creator (from_agent).
    Validates that the from_agent exists in the relay_agents table.
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['from', 'to', 'type', 'amount', 'term']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        from_agent = data['from']
        
        # Authentication: require X-Agent-Key header matching from_agent
        agent_key = request.headers.get('X-Agent-Key', '')
        if not agent_key:
            return jsonify({'error': 'Missing X-Agent-Key header — authentication required'}), 401
        
        if agent_key != from_agent:
            return jsonify({
                'error': 'Unauthorized — X-Agent-Key does not match from_agent'
            }), 403
        
        # Verify from_agent exists in relay_agents table
        db = get_db()
        existing = db.execute(
            "SELECT agent_id FROM relay_agents WHERE agent_id = ?",
            (from_agent,)
        ).fetchone()
        if not existing:
            return jsonify({
                'error': f'from_agent not found: {from_agent}'
            }), 400
        
        # Generate contract ID
        contract_id = f"ctr_{int(time.time())}_{hashlib.blake2b(str(time.time()).encode(), digest_size=4).hexdigest()}"
        
        contract = {
            'id': contract_id,
            'from': data['from'],
            'to': data['to'],
            'type': data['type'],
            'amount': float(data['amount']),
            'currency': data.get('currency', 'RTC'),
            'term': data['term'],
            'state': 'offered',  # Initial state
            'created_at': int(time.time()),
        }
        
        # Store in database
        db = get_db()
        db.execute(
            """INSERT INTO beacon_contracts 
               (id, from_agent, to_agent, type, amount, currency, term, state, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (contract['id'], contract['from'], contract['to'], contract['type'],
             contract['amount'], contract['currency'], contract['term'],
             contract['state'], contract['created_at'])
        )
        db.commit()
        
        return jsonify(contract), 201
        
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/api/contracts/<contract_id>', methods=['PUT'])
def update_contract(contract_id):
    """Update contract state (accept, complete, breach).
    
    Requires X-Agent-Key header to verify caller is a party to the contract.
    Validates state transitions to prevent invalid jumps.
    """
    try:
        data = request.get_json()
        new_state = data.get('state')
        
        if not new_state:
            return jsonify({'error': 'Missing state field'}), 400
        
        valid_states = {'offered', 'active', 'renewed', 'completed', 'breached', 'expired'}
        if new_state not in valid_states:
            return jsonify({'error': f'Invalid state: {new_state}'}), 400
        
        # Valid state transitions — prevent arbitrary jumps
        allowed_transitions = {
            'offered': {'active', 'rejected', 'expired'},
            'active': {'completed', 'breached', 'renewed'},
            'renewed': {'completed', 'breached', 'expired'},
            'completed': set(),  # terminal state
            'breached': set(),   # terminal state
            'expired': set(),    # terminal state
        }
        
        db = get_db()
        
        # Fetch current contract to verify ownership and current state
        contract = db.execute(
            "SELECT id, from_agent, to_agent, state FROM beacon_contracts WHERE id = ?",
            (contract_id,)
        ).fetchone()
        
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        current_state = contract['state']
        
        # Validate state transition
        if new_state not in allowed_transitions.get(current_state, set()):
            return jsonify({
                'error': f'Invalid state transition: {current_state} -> {new_state}'
            }), 400
        
        # Verify caller is a party to the contract
        agent_key = request.headers.get('X-Agent-Key', '')
        if not agent_key:
            return jsonify({'error': 'Missing X-Agent-Key header — authentication required'}), 401
        
        from_agent = contract['from_agent']
        to_agent = contract['to_agent'] if 'to_agent' in contract.keys() else ''
        
        # Caller must be either the from_agent or to_agent
        if agent_key != from_agent and agent_key != to_agent:
            return jsonify({
                'error': 'Unauthorized — caller is not a party to this contract'
            }), 403
        
        # Additional: only to_agent can accept (offered -> active)
        if current_state == 'offered' and new_state == 'active':
            if agent_key != to_agent:
                return jsonify({
                    'error': 'Only the recipient (to_agent) can accept this contract'
                }), 403
        
        # Only from_agent can mark as breached
        if new_state == 'breached':
            if agent_key != from_agent:
                return jsonify({
                    'error': 'Only the contract creator (from_agent) can mark as breached'
                }), 403
        
        db.execute(
            "UPDATE beacon_contracts SET state = ?, updated_at = ? WHERE id = ?",
            (new_state, int(time.time()), contract_id)
        )
        db.commit()
        
        return jsonify({'ok': True, 'contract_id': contract_id, 'state': new_state})
        
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


# ============================================================
# BOUNTIES ENDPOINTS
# ============================================================

@beacon_api.route('/api/bounties', methods=['GET'])
def get_bounties():
    """Get all active bounties (from cache or DB)."""
    try:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM beacon_bounties WHERE state = 'open' ORDER BY reward_rtc DESC"
        ).fetchall()
        
        bounties = []
        for row in rows:
            bounties.append({
                'id': row['id'],
                'ghNum': f"#{row['github_number']}" if row['github_number'] else '',
                'title': row['title'],
                'reward': f"{row['reward_rtc']} RTC" if row['reward_rtc'] else row['reward_text'],
                'reward_rtc': row['reward_rtc'],
                'difficulty': row['difficulty'] or 'ANY',
                'repo': row['github_repo'],
                'url': row['github_url'],
                'state': row['state'],
                'claimant': row['claimant_agent'],
                'completed_by': row['completed_by'],
                'desc': row['description'] or '',
            })
        
        return jsonify(bounties)
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/api/bounties/sync', methods=['POST'])
def sync_bounties():
    """Sync bounties from GitHub API."""
    try:
        import urllib.request
        import ssl
        import hmac

        admin_key = os.environ.get("RC_ADMIN_KEY", "")
        if not admin_key:
            return jsonify({'error': 'RC_ADMIN_KEY not configured — endpoint disabled'}), 503
        provided_key = request.headers.get("X-Admin-Key", "")
        if not hmac.compare_digest(provided_key, admin_key):
            return jsonify({'error': 'Unauthorized — admin key required to sync bounties'}), 401
        
        # GitHub repos to scan
        repos = [
            {'owner': 'Scottcjn', 'repo': 'rustchain-bounties'},
            {'owner': 'Scottcjn', 'repo': 'Rustchain'},
            {'owner': 'Scottcjn', 'repo': 'bottube'},
        ]
        
        all_bounties = []
        
        # SSL verification: enabled by default, set RC_DISABLE_SSL_VERIFY=1 to skip
        ctx = ssl.create_default_context()
        if os.environ.get('RC_DISABLE_SSL_VERIFY', '0') == '1':
            import logging
            logging.warning('[beacon_api] SSL verification disabled via RC_DISABLE_SSL_VERIFY — not recommended for production')
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        
        for repo in repos:
            try:
                url = f"https://api.github.com/repos/{repo['owner']}/{repo['repo']}/issues?state=open&labels=bounty&per_page=30"
                
                req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github.v3+json'})
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    issues = json.loads(resp.read().decode())
                
                for issue in issues:
                    if 'pull_request' in issue:
                        continue
                    
                    # Extract reward from title
                    reward_text = None
                    reward_rtc = None
                    import re
                    match = re.search(r'\((?:Pool:\s*)?(\d[\d,.\-\/a-z ]*RTC[^)]*)\)', issue['title'], re.IGNORECASE)
                    if match:
                        reward_text = match.group(1).strip()
                        # Try to extract numeric value
                        num_match = re.search(r'(\d+(?:\.\d+)?)', reward_text)
                        if num_match:
                            reward_rtc = float(num_match.group(1).replace(',', ''))
                    
                    if not reward_text:
                        continue
                    
                    # Determine difficulty from labels
                    difficulty = 'ANY'
                    label_map = {
                        'good first issue': 'EASY', 'easy': 'EASY', 'micro': 'EASY',
                        'standard': 'MEDIUM', 'feature': 'MEDIUM', 'integration': 'MEDIUM',
                        'major': 'HARD', 'critical': 'HARD', 'red-team': 'HARD',
                    }
                    for label in issue.get('labels', []):
                        label_name = label.get('name', '').lower()
                        if label_name in label_map:
                            difficulty = label_map[label_name]
                            break
                    
                    bounty = {
                        'id': f"gh_{repo['repo']}_{issue['number']}",
                        'github_number': issue['number'],
                        'title': issue['title'],
                        'reward_rtc': reward_rtc,
                        'reward_text': reward_text,
                        'difficulty': difficulty,
                        'github_repo': f"{repo['owner']}/{repo['repo']}",
                        'github_url': issue['html_url'],
                        'state': 'open',
                        'description': issue.get('body', '')[:500] if issue.get('body') else '',
                        'labels': json.dumps([l['name'] for l in issue.get('labels', [])]),
                        'created_at': int(time.time()),
                    }
                    all_bounties.append(bounty)
                
            except Exception as e:
                print(f"Failed to fetch bounties from {repo['repo']}: {e}")
                continue
        
        # Store in database
        db = get_db()
        for bounty in all_bounties:
            db.execute(
                """INSERT OR REPLACE INTO beacon_bounties 
                   (id, github_number, title, reward_rtc, reward_text, difficulty, 
                    github_repo, github_url, state, description, labels, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (bounty['id'], bounty['github_number'], bounty['title'],
                 bounty['reward_rtc'], bounty['reward_text'], bounty['difficulty'],
                 bounty['github_repo'], bounty['github_url'], bounty['state'],
                 bounty['description'], bounty['labels'], bounty['created_at'], bounty['created_at'])
            )
        
        db.commit()
        
        return jsonify({'synced': len(all_bounties), 'ok': True})
        
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/api/bounties/<bounty_id>/claim', methods=['POST'])
def claim_bounty(bounty_id):
    """Claim a bounty for an agent (admin-only)."""
    try:
        import os, hmac
        admin_key = os.environ.get("RC_ADMIN_KEY", "")
        if not admin_key:
            return jsonify({'error': 'RC_ADMIN_KEY not configured — endpoint disabled'}), 503
        provided_key = request.headers.get("X-Admin-Key", "")
        if not hmac.compare_digest(provided_key, admin_key):
            return jsonify({'error': 'Unauthorized — admin key required to claim bounties'}), 401

        data = request.get_json()
        agent_id = data.get('agent_id')
        
        if not agent_id:
            return jsonify({'error': 'Missing agent_id'}), 400
        
        db = get_db()
        db.execute(
            "UPDATE beacon_bounties SET state = 'claimed', claimant_agent = ?, updated_at = ? WHERE id = ?",
            (agent_id, int(time.time()), bounty_id)
        )
        db.commit()
        
        if db.total_changes == 0:
            return jsonify({'error': 'Bounty not found'}), 404
        
        return jsonify({'ok': True, 'bounty_id': bounty_id, 'claimant': agent_id})
        
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/api/bounties/<bounty_id>/complete', methods=['POST'])
def complete_bounty(bounty_id):
    """Mark bounty as completed by an agent (admin-only)."""
    try:
        import os, hmac
        admin_key = os.environ.get("RC_ADMIN_KEY", "")
        if not admin_key:
            return jsonify({'error': 'RC_ADMIN_KEY not configured — endpoint disabled'}), 503
        provided_key = request.headers.get("X-Admin-Key", "")
        if not hmac.compare_digest(provided_key, admin_key):
            return jsonify({'error': 'Unauthorized — admin key required to complete bounties'}), 401

        data = request.get_json()
        agent_id = data.get('agent_id')
        
        if not agent_id:
            return jsonify({'error': 'Missing agent_id'}), 400
        
        db = get_db()

        # Verify bounty exists and is in claimable state
        bounty = db.execute(
            "SELECT state, claimant_agent FROM beacon_bounties WHERE id = ?",
            (bounty_id,)
        ).fetchone()
        if not bounty:
            return jsonify({'error': 'Bounty not found'}), 404
        if bounty['state'] == 'completed':
            return jsonify({'error': 'Bounty already completed'}), 409

        db.execute(
            "UPDATE beacon_bounties SET state = 'completed', completed_by = ?, updated_at = ? WHERE id = ?",
            (agent_id, int(time.time()), bounty_id)
        )
        db.commit()
        
        # Update agent reputation
        rep = db.execute("SELECT * FROM beacon_reputation WHERE agent_id = ?", (agent_id,)).fetchone()
        if rep:
            db.execute(
                "UPDATE beacon_reputation SET bounties_completed = bounties_completed + 1, score = score + 10, last_updated = ? WHERE agent_id = ?",
                (int(time.time()), agent_id)
            )
        else:
            db.execute(
                "INSERT INTO beacon_reputation (agent_id, bounties_completed, score, last_updated) VALUES (?, 1, 10, ?)",
                (agent_id, int(time.time()))
            )
        db.commit()
        
        return jsonify({'ok': True, 'bounty_id': bounty_id, 'completed_by': agent_id})
        
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


# ============================================================
# REPUTATION ENDPOINTS
# ============================================================

@beacon_api.route('/api/reputation', methods=['GET'])
def get_reputation():
    """Get all agent reputations."""
    try:
        db = get_db()
        rows = db.execute("SELECT * FROM beacon_reputation ORDER BY score DESC").fetchall()
        
        reputations = []
        for row in rows:
            reputations.append({
                'agent_id': row['agent_id'],
                'score': row['score'],
                'bounties_completed': row['bounties_completed'],
                'contracts_completed': row['contracts_completed'],
                'contracts_breached': row['contracts_breached'],
                'total_rtc_earned': row['total_rtc_earned'],
            })
        
        return jsonify(reputations)
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


@beacon_api.route('/api/reputation/<agent_id>', methods=['GET'])
def get_agent_reputation(agent_id):
    """Get single agent reputation."""
    try:
        db = get_db()
        row = db.execute("SELECT * FROM beacon_reputation WHERE agent_id = ?", (agent_id,)).fetchone()
        
        if not row:
            return jsonify({'error': 'Agent not found'}), 404
        
        return jsonify({
            'agent_id': row['agent_id'],
            'score': row['score'],
            'bounties_completed': row['bounties_completed'],
            'contracts_completed': row['contracts_completed'],
            'contracts_breached': row['contracts_breached'],
            'total_rtc_earned': row['total_rtc_earned'],
        })
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


# ============================================================
# CHAT ENDPOINT
# ============================================================

@beacon_api.route('/api/chat', methods=['POST'])
def chat():
    """Send message to an agent (mock response for demo)."""
    try:
        data = request.get_json()
        agent_id = data.get('agent_id')
        message = data.get('message')
        
        if not agent_id or not message:
            return jsonify({'error': 'Missing agent_id or message'}), 400
        
        # Store user message
        db = get_db()
        db.execute(
            "INSERT INTO beacon_chat (agent_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (agent_id, 'user', message, int(time.time()))
        )
        
        # Generate mock response (in production, call LLM)
        responses = [
            f"Acknowledged. I am {agent_id}. How can I assist?",
            "Transmission received. Processing request...",
            "Beacon signal strong. Standing by for instructions.",
            "Contract terms acceptable. Ready to proceed.",
            "Reputation check complete. Trust level adequate.",
        ]
        import random
        response = random.choice(responses)
        
        # Store agent response
        db.execute(
            "INSERT INTO beacon_chat (agent_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (agent_id, 'assistant', response, int(time.time()))
        )
        db.commit()
        
        return jsonify({
            'response': response,
            'agent': agent_id,
            'timestamp': int(time.time()),
        })
        
    except Exception as e:
        return jsonify({'error': 'internal_error'}), 500


# ============================================================
# RELAY DISCOVERY ENDPOINT
# ============================================================

@beacon_api.route('/relay/discover', methods=['GET'])
def relay_discover():
    """Discover relay agents (for 3D visualization)."""
    # In production, query the relay registry
    # For demo, return empty array
    return jsonify([])


# ============================================================
# HEALTH CHECK
# ============================================================

@beacon_api.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'timestamp': int(time.time()),
        'service': 'beacon-atlas-api',
    })
