// SPDX-License-Identifier: Apache-2.0


use std::time::{SystemTime, UNIX_EPOCH};
use serde::{Serialize, Deserialize};
use log::{info, warn, error};

/// Security utilities module
pub struct SecurityUtils;

impl SecurityUtils {
    /// Get current timestamp in seconds since epoch
    pub fn get_current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_else(|_| std::time::Duration::from_secs(0))
            .as_secs()
    }

    /// Validate input to prevent injection attacks
    pub fn validate_input(input: &str, max_length: usize) -> Result<(), String> {
        if input.is_empty() {
            return Err("Input cannot be empty".to_string());
        }

        if input.len() > max_length {
            return Err(format!("Input exceeds maximum length of {}", max_length));
        }

        // Check for potentially dangerous characters
        let dangerous_chars = [';', '\'', '\"', '\\', '<', '>', '&', '|', '$', '`'];
        if input.chars().any(|c| dangerous_chars.contains(&c)) {
            return Err("Input contains potentially dangerous characters".to_string());
        }

        Ok(())
    }

    /// Sanitize input to prevent XSS and injection attacks
    pub fn sanitize_input(input: &str) -> String {
        input
            .replace('&', "&amp;")
            .replace('<', "&lt;")
            .replace('>', "&gt;")
            .replace('"', "&quot;")
            .replace('\'', "&#39;")
    }

    /// Generate a secure random string
    pub fn generate_secure_random_string(length: usize) -> String {
        use rand::{Rng, rngs::OsRng};
        use rand::distributions::Alphanumeric;

        OsRng
            .sample_iter(&Alphanumeric)
            .take(length)
            .map(char::from)
            .collect()
    }

    /// Check if a string is a valid UUID
    pub fn is_valid_uuid(uuid: &str) -> bool {
        uuid.len() == 36 &&
        uuid.chars().filter(|&c| c == '-').count() == 4 &&
        uuid.chars().all(|c| c.is_ascii_hexdigit() || c == '-')
    }

    /// Generate a secure token
    pub fn generate_secure_token(length: usize) -> String {
        use rand::{Rng, rngs::OsRng};
        use rand::distributions::{Alphanumeric, DistString};

        Alphanumeric.sample_string(&mut OsRng, length)
    }

    /// Constant-time comparison to prevent timing attacks
    pub fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
        if a.len() != b.len() {
            return false;
        }

        let mut result = 0;
        for (x, y) in a.iter().zip(b.iter()) {
            result |= x ^ y;
        }

        result == 0
    }

    /// Log security event
    pub fn log_security_event(event_type: &str, message: &str, severity: &str) {
        let timestamp = Self::get_current_timestamp();

        match severity.to_lowercase().as_str() {
            "info" => info!("[{}] {}: {}", timestamp, event_type, message),
            "warn" => warn!("[{}] {}: {}", timestamp, event_type, message),
            "error" => error!("[{}] {}: {}", timestamp, event_type, message),
            _ => info!("[{}] {}: {}", timestamp, event_type, message),
        }
    }
}

/// Security configuration
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SecurityConfig {
    pub max_input_length: usize,
    pub require_secure_connections: bool,
    pub enable_audit_logging: bool,
    pub audit_log_path: String,
    pub enable_rate_limiting: bool,
    pub max_requests_per_minute: u32,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        SecurityConfig {
            max_input_length: 1024,
            require_secure_connections: true,
            enable_audit_logging: true,
            audit_log_path: "security_audit.log".to_string(),
            enable_rate_limiting: true,
            max_requests_per_minute: 100,
        }
    }
}

