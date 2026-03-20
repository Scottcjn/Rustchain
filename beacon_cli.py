// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import sys
from datetime import datetime, timedelta
from flask import Flask
import click

DB_PATH = 'rustchain.db'

def init_db():
    """Initialize beacon keys table if it doesn't exist"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS beacon_keys (
                agent_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                rotation_count INTEGER DEFAULT 0,
                revoked INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

def get_flask_app():
    """Get Flask app instance with context"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app

@click.group()
def beacon():
    """Beacon key management commands"""
    pass

@beacon.group()
def keys():
    """Beacon key operations"""
    pass

@keys.command('list')
def list_keys():
    """List all beacon keys with metadata"""
    init_db()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT agent_id, public_key, first_seen, last_seen,
                   rotation_count, revoked
            FROM beacon_keys
            ORDER BY last_seen DESC
        ''')
        rows = cursor.fetchall()

    if not rows:
        click.echo("No beacon keys found.")
        return

    click.echo(f"{'Agent ID':<20} {'Key (truncated)':<20} {'First Seen':<20} {'Last Seen':<20} {'Rotations':<10} {'Status':<10}")
    click.echo("-" * 110)

    for row in rows:
        agent_id, pubkey, first_seen, last_seen, rotations, revoked = row
        key_short = pubkey[:16] + "..." if len(pubkey) > 19 else pubkey
        status = "REVOKED" if revoked else "ACTIVE"

        # Check if key is expired (30 days without heartbeat)
        try:
            last_dt = datetime.fromisoformat(last_seen)
            if datetime.now() - last_dt > timedelta(days=30):
                status = "EXPIRED"
        except:
            pass

        click.echo(f"{agent_id:<20} {key_short:<20} {first_seen:<20} {last_seen:<20} {rotations:<10} {status:<10}")

@keys.command('revoke')
@click.argument('agent_id')
def revoke_key(agent_id):
    """Revoke a beacon key for specified agent"""
    init_db()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT agent_id FROM beacon_keys WHERE agent_id = ?', (agent_id,))
        if not cursor.fetchone():
            click.echo(f"Error: Agent ID '{agent_id}' not found.")
            return

        conn.execute(
            'UPDATE beacon_keys SET revoked = 1 WHERE agent_id = ?',
            (agent_id,)
        )
        conn.commit()

    click.echo(f"Key for agent '{agent_id}' has been revoked.")

@keys.command('rotate')
@click.option('--agent-id', required=True, help='Agent ID to rotate key for')
@click.option('--new-key', required=True, help='New public key')
@click.option('--signature', help='Signature from old key authorizing rotation')
def rotate_key(agent_id, new_key, signature):
    """Rotate beacon key for an agent"""
    init_db()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            'SELECT public_key, revoked FROM beacon_keys WHERE agent_id = ?',
            (agent_id,)
        )
        result = cursor.fetchone()

        if not result:
            click.echo(f"Error: Agent ID '{agent_id}' not found.")
            return

        old_key, revoked = result
        if revoked:
            click.echo(f"Error: Agent '{agent_id}' key is revoked. Cannot rotate.")
            return

        if signature:
            # TODO: Verify signature of new_key using old_key
            click.echo("Signature verification not yet implemented - proceeding with rotation.")

        now = datetime.now().isoformat()
        conn.execute('''
            UPDATE beacon_keys
            SET public_key = ?, last_seen = ?, rotation_count = rotation_count + 1
            WHERE agent_id = ?
        ''', (new_key, now, agent_id))
        conn.commit()

    click.echo(f"Key rotated for agent '{agent_id}'.")

@keys.command('cleanup')
@click.option('--days', default=30, help='Remove keys not seen for this many days')
@click.option('--dry-run', is_flag=True, help='Show what would be removed without deleting')
def cleanup_keys(days, dry_run):
    """Remove expired beacon keys"""
    init_db()
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff.isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            'SELECT agent_id, last_seen FROM beacon_keys WHERE last_seen < ? AND revoked = 0',
            (cutoff_str,)
        )
        expired_keys = cursor.fetchall()

        if not expired_keys:
            click.echo("No expired keys found.")
            return

        if dry_run:
            click.echo(f"Would remove {len(expired_keys)} expired keys:")
            for agent_id, last_seen in expired_keys:
                click.echo(f"  {agent_id} (last seen: {last_seen})")
        else:
            conn.execute(
                'DELETE FROM beacon_keys WHERE last_seen < ? AND revoked = 0',
                (cutoff_str,)
            )
            conn.commit()
            click.echo(f"Removed {len(expired_keys)} expired keys.")

if __name__ == '__main__':
    # Create Flask app context for database operations
    app = get_flask_app()
    with app.app_context():
        beacon()
