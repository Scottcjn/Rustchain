// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import os
from typing import Dict, Optional
from flask import request, session

DB_PATH = 'rustchain.db'

class LocalizedErrors:
    def __init__(self):
        self.translations = {}
        self.default_locale = 'en'
        self.load_translations()
        
    def load_translations(self):
        """Load all translation files from i18n directory"""
        i18n_dir = 'i18n'
        if not os.path.exists(i18n_dir):
            os.makedirs(i18n_dir)
            
        for filename in os.listdir(i18n_dir):
            if filename.endswith('.json'):
                lang_code = filename[:-5]
                try:
                    with open(os.path.join(i18n_dir, filename), 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                except Exception:
                    continue
                    
    def get_user_locale(self) -> str:
        """Get user locale from session, headers, or default"""
        if 'locale' in session:
            return session['locale']
            
        if request and request.headers.get('Accept-Language'):
            accepted = request.headers.get('Accept-Language', '').split(',')
            for lang in accepted:
                lang_code = lang.split(';')[0].strip()[:2]
                if lang_code in self.translations:
                    return lang_code
                    
        return self.default_locale
        
    def get_error_message(self, error_key: str, locale: str = None, **kwargs) -> str:
        """Get localized error message"""
        if not locale:
            locale = self.get_user_locale()
            
        if locale in self.translations and error_key in self.translations[locale]:
            message = self.translations[locale][error_key]
        elif error_key in self.translations.get(self.default_locale, {}):
            message = self.translations[self.default_locale][error_key]
        else:
            message = error_key
            
        try:
            return message.format(**kwargs)
        except KeyError:
            return message
            
    def log_error(self, error_key: str, user_id: str = None, context: Dict = None):
        """Log localized error to database"""
        locale = self.get_user_locale()
        message = self.get_error_message(error_key, locale)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    error_key TEXT,
                    message TEXT,
                    locale TEXT,
                    user_id TEXT,
                    context TEXT
                )
            ''')
            
            context_json = json.dumps(context) if context else None
            conn.execute('''
                INSERT INTO error_logs (error_key, message, locale, user_id, context)
                VALUES (?, ?, ?, ?, ?)
            ''', (error_key, message, locale, user_id, context_json))

localized_errors = LocalizedErrors()

def get_localized_error(error_key: str, **kwargs) -> str:
    """Helper function to get localized error message"""
    return localized_errors.get_error_message(error_key, **kwargs)

def create_default_translations():
    """Create default English translation file"""
    i18n_dir = 'i18n'
    if not os.path.exists(i18n_dir):
        os.makedirs(i18n_dir)
        
    en_translations = {
        "insufficient_balance": "Insufficient balance: required {required}, available {available}",
        "invalid_address": "Invalid wallet address format",
        "transaction_failed": "Transaction failed: {reason}",
        "network_error": "Network connection error",
        "mining_error": "Mining operation failed",
        "wallet_not_found": "Wallet not found",
        "invalid_private_key": "Invalid private key format",
        "block_validation_failed": "Block validation failed",
        "consensus_error": "Consensus mechanism error",
        "database_error": "Database operation failed",
        "authentication_failed": "Authentication failed",
        "permission_denied": "Permission denied",
        "rate_limit_exceeded": "Rate limit exceeded, try again later",
        "invalid_input": "Invalid input data",
        "timeout_error": "Operation timeout",
        "peer_connection_failed": "Failed to connect to peer",
        "blockchain_sync_error": "Blockchain synchronization error",
        "invalid_signature": "Invalid transaction signature",
        "double_spend_detected": "Double spending attempt detected",
        "mempool_full": "Transaction mempool is full",
        "fee_too_low": "Transaction fee too low",
        "block_size_exceeded": "Block size limit exceeded",
        "invalid_nonce": "Invalid proof of work nonce",
        "chain_reorganization": "Blockchain reorganization in progress",
        "wallet_locked": "Wallet is locked, please unlock first"
    }
    
    with open(os.path.join(i18n_dir, 'en.json'), 'w', encoding='utf-8') as f:
        json.dump(en_translations, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    create_default_translations()