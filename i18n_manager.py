// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import os
import locale
from typing import Dict, Optional, Any
from contextlib import contextmanager

DB_PATH = 'rustchain.db'
I18N_DIR = 'i18n'

class I18nManager:
    def __init__(self):
        self.translations = {}
        self.current_language = 'en'
        self.fallback_language = 'en'
        self._init_db()
        self._load_translations()
        self._detect_user_language()

    def _init_db(self):
        """Initialize user preferences table for language settings"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT UNIQUE,
                    language_code TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def _load_translations(self):
        """Load all available translation files from i18n directory"""
        if not os.path.exists(I18N_DIR):
            os.makedirs(I18N_DIR)
            self._create_default_translations()

        for filename in os.listdir(I18N_DIR):
            if filename.endswith('.json'):
                lang_code = filename[:-5]
                file_path = os.path.join(I18N_DIR, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error loading translation file {filename}: {e}")

    def _create_default_translations(self):
        """Create default English translation file"""
        default_translations = {
            "error.invalid_transaction": "Invalid transaction format",
            "error.insufficient_balance": "Insufficient balance for transaction",
            "error.connection_failed": "Failed to connect to network",
            "error.block_validation_failed": "Block validation failed",
            "error.mining_error": "Mining operation failed",
            "error.wallet_locked": "Wallet is locked",
            "error.invalid_address": "Invalid wallet address",
            "error.transaction_timeout": "Transaction timed out",
            "error.network_unreachable": "Network unreachable",
            "error.file_not_found": "Required file not found",
            "error.permission_denied": "Permission denied",
            "error.database_error": "Database operation failed",
            "error.invalid_signature": "Invalid transaction signature",
            "error.duplicate_transaction": "Duplicate transaction detected",
            "error.chain_sync_failed": "Blockchain synchronization failed",
            "error.peer_connection_lost": "Lost connection to peer",
            "error.invalid_block_height": "Invalid block height",
            "error.merkle_root_mismatch": "Merkle root verification failed",
            "error.nonce_invalid": "Invalid proof of work nonce",
            "error.gas_limit_exceeded": "Transaction gas limit exceeded",
            "success.transaction_sent": "Transaction sent successfully",
            "success.block_mined": "Block mined successfully",
            "success.wallet_created": "Wallet created successfully",
            "info.mining_started": "Mining process started",
            "info.syncing_blockchain": "Synchronizing blockchain..."
        }

        en_file = os.path.join(I18N_DIR, 'en.json')
        with open(en_file, 'w', encoding='utf-8') as f:
            json.dump(default_translations, f, indent=2, ensure_ascii=False)

    def _detect_user_language(self):
        """Detect user's preferred language from system locale"""
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                lang_code = system_locale.split('_')[0]
                if lang_code in self.translations:
                    self.current_language = lang_code
        except:
            pass

    def set_user_language(self, user_id: str, lang_code: str):
        """Set language preference for a specific user"""
        if lang_code not in self.translations:
            return False

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO user_preferences (user_id, language_code, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, lang_code))
            conn.commit()

        return True

    def get_user_language(self, user_id: str) -> str:
        """Get language preference for a specific user"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                'SELECT language_code FROM user_preferences WHERE user_id = ?',
                (user_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else self.current_language

    def translate(self, key: str, user_id: Optional[str] = None, **kwargs) -> str:
        """Translate a message key to the appropriate language"""
        lang = self.get_user_language(user_id) if user_id else self.current_language

        # Try current language first
        if lang in self.translations and key in self.translations[lang]:
            message = self.translations[lang][key]
        # Fall back to default language
        elif self.fallback_language in self.translations and key in self.translations[self.fallback_language]:
            message = self.translations[self.fallback_language][key]
        # Return key if no translation found
        else:
            return key

        # Replace placeholders if kwargs provided
        try:
            return message.format(**kwargs) if kwargs else message
        except (KeyError, ValueError):
            return message

    def get_available_languages(self) -> Dict[str, str]:
        """Get list of available languages with their names"""
        language_names = {
            'en': 'English',
            'es': 'Español',
            'fr': 'Français',
            'de': 'Deutsch',
            'it': 'Italiano',
            'pt': 'Português',
            'ru': 'Русский',
            'zh': '中文',
            'ja': '日本語',
            'ko': '한국어'
        }

        available = {}
        for lang_code in self.translations.keys():
            available[lang_code] = language_names.get(lang_code, lang_code.upper())

        return available

    def add_translation(self, lang_code: str, translations: Dict[str, str]):
        """Add new translations for a language"""
        file_path = os.path.join(I18N_DIR, f'{lang_code}.json')

        # Load existing translations if file exists
        existing = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except:
                pass

        # Merge with new translations
        existing.update(translations)

        # Save to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        # Update in-memory translations
        self.translations[lang_code] = existing

    def get_translation_stats(self) -> Dict[str, Any]:
        """Get statistics about translation coverage"""
        if not self.translations:
            return {}

        base_keys = set(self.translations.get(self.fallback_language, {}).keys())
        stats = {}

        for lang_code, translations in self.translations.items():
            translated_keys = set(translations.keys())
            coverage = len(translated_keys & base_keys) / len(base_keys) if base_keys else 0

            stats[lang_code] = {
                'total_strings': len(translations),
                'coverage_percent': round(coverage * 100, 2),
                'missing_keys': list(base_keys - translated_keys)
            }

        return stats

# Global instance
i18n = I18nManager()

# Convenience functions
def t(key: str, user_id: Optional[str] = None, **kwargs) -> str:
    """Shorthand translation function"""
    return i18n.translate(key, user_id, **kwargs)

def translate_error(error_key: str, user_id: Optional[str] = None, **kwargs) -> str:
    """Translate error messages with error. prefix"""
    if not error_key.startswith('error.'):
        error_key = f'error.{error_key}'
    return i18n.translate(error_key, user_id, **kwargs)

def set_language(user_id: str, lang_code: str) -> bool:
    """Set user language preference"""
    return i18n.set_user_language(user_id, lang_code)
