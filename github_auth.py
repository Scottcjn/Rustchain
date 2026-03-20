// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sqlite3
import requests
import secrets
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode
from flask import request, session, redirect, url_for, jsonify

DB_PATH = 'faucet.db'
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
GITHUB_AUTH_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_API_URL = 'https://api.github.com'

def init_github_auth_tables():
    """Initialize database tables for GitHub OAuth"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS github_auth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS github_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                github_id INTEGER UNIQUE NOT NULL,
                username TEXT NOT NULL,
                email TEXT,
                account_created_at TIMESTAMP,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_token TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS faucet_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                github_username TEXT,
                github_id INTEGER,
                amount REAL DEFAULT 1.0,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                tx_hash TEXT
            )
        ''')

def generate_github_auth_url(redirect_uri):
    """Generate GitHub OAuth authorization URL"""
    if not GITHUB_CLIENT_ID:
        raise ValueError("GitHub OAuth not configured")

    state = secrets.token_urlsafe(32)

    # Store state in database with expiration
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO github_auth (state, expires_at) VALUES (?, ?)',
            (state, expires_at)
        )

    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'scope': 'user:email',
        'state': state,
        'allow_signup': 'false'
    }

    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"

def verify_github_callback(code, state, redirect_uri):
    """Handle GitHub OAuth callback and exchange code for token"""
    if not code or not state:
        return None, "Missing code or state parameter"

    # Verify state parameter
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            'SELECT expires_at FROM github_auth WHERE state = ?',
            (state,)
        )
        result = cursor.fetchone()

        if not result:
            return None, "Invalid state parameter"

        expires_at = datetime.fromisoformat(result[0])
        if datetime.utcnow() > expires_at:
            return None, "State parameter expired"

        # Clean up used state
        conn.execute('DELETE FROM github_auth WHERE state = ?', (state,))

    # Exchange code for access token
    token_data = {
        'client_id': GITHUB_CLIENT_ID,
        'client_secret': GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': redirect_uri
    }

    headers = {'Accept': 'application/json'}

    try:
        response = requests.post(GITHUB_TOKEN_URL, data=token_data, headers=headers)
        response.raise_for_status()

        token_info = response.json()
        access_token = token_info.get('access_token')

        if not access_token:
            return None, "Failed to get access token"

        # Get user info
        user_info = get_github_user_info(access_token)
        if not user_info:
            return None, "Failed to get user information"

        # Store/update user in database
        github_user = store_github_user(user_info, access_token)
        return github_user, None

    except requests.RequestException as e:
        return None, f"GitHub API error: {str(e)}"

def get_github_user_info(access_token):
    """Fetch user information from GitHub API"""
    headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    try:
        # Get user profile
        user_response = requests.get(f"{GITHUB_API_URL}/user", headers=headers)
        user_response.raise_for_status()
        user_data = user_response.json()

        # Get user emails
        email_response = requests.get(f"{GITHUB_API_URL}/user/emails", headers=headers)
        email_response.raise_for_status()
        emails = email_response.json()

        primary_email = None
        for email in emails:
            if email.get('primary'):
                primary_email = email.get('email')
                break

        return {
            'id': user_data['id'],
            'login': user_data['login'],
            'email': primary_email,
            'created_at': user_data['created_at']
        }

    except requests.RequestException:
        return None

def store_github_user(user_info, access_token):
    """Store or update GitHub user in database"""
    with sqlite3.connect(DB_PATH) as conn:
        # Check if user exists
        cursor = conn.execute(
            'SELECT id, username FROM github_users WHERE github_id = ?',
            (user_info['id'],)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing user
            conn.execute('''
                UPDATE github_users
                SET username = ?, email = ?, access_token = ?, last_updated = CURRENT_TIMESTAMP
                WHERE github_id = ?
            ''', (user_info['login'], user_info['email'], access_token, user_info['id']))

            return {
                'id': existing[0],
                'github_id': user_info['id'],
                'username': user_info['login'],
                'email': user_info['email']
            }
        else:
            # Insert new user
            cursor = conn.execute('''
                INSERT INTO github_users (github_id, username, email, account_created_at, access_token)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_info['id'],
                user_info['login'],
                user_info['email'],
                user_info['created_at'],
                access_token
            ))

            return {
                'id': cursor.lastrowid,
                'github_id': user_info['id'],
                'username': user_info['login'],
                'email': user_info['email']
            }

def get_github_user_by_username(username):
    """Get GitHub user from database by username"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT id, github_id, username, email, account_created_at, verified_at
            FROM github_users WHERE username = ?
        ''', (username,))

        result = cursor.fetchone()
        if result:
            return {
                'id': result[0],
                'github_id': result[1],
                'username': result[2],
                'email': result[3],
                'account_created_at': result[4],
                'verified_at': result[5]
            }
        return None

def check_account_age(github_username, min_age_days=30):
    """Check if GitHub account is old enough"""
    user = get_github_user_by_username(github_username)
    if not user or not user['account_created_at']:
        return False

    created_date = datetime.fromisoformat(user['account_created_at'].replace('Z', '+00:00'))
    age_days = (datetime.utcnow().replace(tzinfo=created_date.tzinfo) - created_date).days

    return age_days >= min_age_days

def can_request_faucet(wallet_address, github_username=None):
    """Check if user can request from faucet based on rate limits"""
    with sqlite3.connect(DB_PATH) as conn:
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        # Check wallet address limit (anonymous users)
        cursor = conn.execute('''
            SELECT COUNT(*) FROM faucet_requests
            WHERE wallet_address = ? AND requested_at > ? AND status != 'failed'
        ''', (wallet_address, cutoff_time))

        wallet_count = cursor.fetchone()[0]
        if wallet_count >= 1 and not github_username:
            return False, "Wallet already used in last 24 hours"

        # Check GitHub user limit (authenticated users get higher limits)
        if github_username:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM faucet_requests
                WHERE github_username = ? AND requested_at > ? AND status != 'failed'
            ''', (github_username, cutoff_time))

            github_count = cursor.fetchone()[0]
            if github_count >= 2:  # Authenticated users get 2 requests per day
                return False, "GitHub account already used twice in last 24 hours"

        return True, None

def record_faucet_request(wallet_address, amount=1.0, github_username=None, github_id=None):
    """Record a new faucet request"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            INSERT INTO faucet_requests (wallet_address, github_username, github_id, amount)
            VALUES (?, ?, ?, ?)
        ''', (wallet_address, github_username, github_id, amount))

        return cursor.lastrowid

def cleanup_expired_states():
    """Clean up expired OAuth states"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM github_auth WHERE expires_at < ?', (datetime.utcnow(),))
