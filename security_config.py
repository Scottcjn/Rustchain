// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import time
from typing import Dict, Any, Optional

class SecurityConfig:
    """Configuration management for attestation security parameters"""

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.config = self._load_default_config()
        if config_override:
            self.config.update(config_override)

    def _load_default_config(self) -> Dict[str, Any]:
        """Load default security configuration with environment variable overrides"""
        return {
            # Nonce management
            'nonce_expiry_seconds': int(os.getenv('NONCE_EXPIRY_SECONDS', '300')),
            'nonce_cleanup_interval': int(os.getenv('NONCE_CLEANUP_INTERVAL', '900')),
            'max_nonce_cache_size': int(os.getenv('MAX_NONCE_CACHE_SIZE', '10000')),

            # Timestamp validation
            'timestamp_tolerance_seconds': int(os.getenv('TIMESTAMP_TOLERANCE_SECONDS', '30')),
            'max_timestamp_skew': int(os.getenv('MAX_TIMESTAMP_SKEW', '120')),
            'require_timestamp_validation': os.getenv('REQUIRE_TIMESTAMP_VALIDATION', 'true').lower() == 'true',

            # Challenge-response settings
            'enable_challenge_response': os.getenv('ENABLE_CHALLENGE_RESPONSE', 'false').lower() == 'true',
            'challenge_length_bytes': int(os.getenv('CHALLENGE_LENGTH_BYTES', '32')),
            'challenge_expiry_seconds': int(os.getenv('CHALLENGE_EXPIRY_SECONDS', '180')),

            # Backward compatibility
            'legacy_mode_enabled': os.getenv('LEGACY_MODE_ENABLED', 'true').lower() == 'true',
            'legacy_grace_period_days': int(os.getenv('LEGACY_GRACE_PERIOD_DAYS', '30')),
            'strict_validation_after': int(os.getenv('STRICT_VALIDATION_AFTER', str(int(time.time()) + 2592000))),

            # Rate limiting and abuse prevention
            'max_attestations_per_minute': int(os.getenv('MAX_ATTESTATIONS_PER_MINUTE', '10')),
            'failed_attempt_penalty_seconds': int(os.getenv('FAILED_ATTEMPT_PENALTY_SECONDS', '60')),
            'max_consecutive_failures': int(os.getenv('MAX_CONSECUTIVE_FAILURES', '5')),

            # Database cleanup
            'attestation_retention_days': int(os.getenv('ATTESTATION_RETENTION_DAYS', '7')),
            'cleanup_batch_size': int(os.getenv('CLEANUP_BATCH_SIZE', '1000')),
            'auto_cleanup_enabled': os.getenv('AUTO_CLEANUP_ENABLED', 'true').lower() == 'true',

            # Security features
            'enforce_nonce_uniqueness': os.getenv('ENFORCE_NONCE_UNIQUENESS', 'true').lower() == 'true',
            'require_secure_random_nonces': os.getenv('REQUIRE_SECURE_RANDOM_NONCES', 'true').lower() == 'true',
            'log_security_events': os.getenv('LOG_SECURITY_EVENTS', 'true').lower() == 'true',
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default"""
        return self.config.get(key, default)

    def is_legacy_mode_active(self) -> bool:
        """Check if legacy compatibility mode is currently active"""
        if not self.config['legacy_mode_enabled']:
            return False
        return time.time() < self.config['strict_validation_after']

    def should_enforce_nonce_binding(self) -> bool:
        """Determine if nonce binding should be enforced based on current settings"""
        if self.is_legacy_mode_active():
            return not self.config['legacy_mode_enabled']
        return self.config['enforce_nonce_uniqueness']

    def get_nonce_window_bounds(self) -> tuple[int, int]:
        """Calculate valid nonce timestamp window boundaries"""
        now = int(time.time())
        tolerance = self.config['timestamp_tolerance_seconds']
        max_skew = self.config['max_timestamp_skew']

        earliest_valid = now - max_skew - tolerance
        latest_valid = now + tolerance

        return earliest_valid, latest_valid

    def validate_config(self) -> bool:
        """Validate configuration parameters for consistency"""
        errors = []

        if self.config['nonce_expiry_seconds'] <= 0:
            errors.append("nonce_expiry_seconds must be positive")

        if self.config['timestamp_tolerance_seconds'] < 0:
            errors.append("timestamp_tolerance_seconds cannot be negative")

        if self.config['challenge_expiry_seconds'] <= self.config['timestamp_tolerance_seconds']:
            errors.append("challenge_expiry_seconds should be greater than timestamp_tolerance_seconds")

        if self.config['max_nonce_cache_size'] <= 0:
            errors.append("max_nonce_cache_size must be positive")

        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

        return True

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values and validate"""
        old_config = self.config.copy()
        self.config.update(updates)

        try:
            self.validate_config()
        except ValueError:
            self.config = old_config
            raise

    def export_for_client(self) -> Dict[str, Any]:
        """Export client-safe configuration subset"""
        client_keys = [
            'nonce_expiry_seconds',
            'timestamp_tolerance_seconds',
            'enable_challenge_response',
            'challenge_length_bytes',
            'legacy_mode_enabled'
        ]

        return {key: self.config[key] for key in client_keys if key in self.config}

# Global configuration instance
security_config = SecurityConfig()

def get_security_config() -> SecurityConfig:
    """Get the global security configuration instance"""
    return security_config

def reload_security_config(config_override: Optional[Dict[str, Any]] = None) -> SecurityConfig:
    """Reload global security configuration"""
    global security_config
    security_config = SecurityConfig(config_override)
    return security_config
