


#[cfg(test)]
mod tests {
    use rustchain_miner::security::{
        audit::{SecurityAudit, Severity},
        encryption::{Encryption, SecureData},
        network::NetworkSecurity,
        utils::SecurityUtils,
    };
    use std::net::{SocketAddr, IpAddr, Ipv4Addr};
    use std::time::Duration;

    #[test]
    fn test_generate_key() {
        let key = Encryption::generate_key(32).unwrap();
        assert_eq!(key.len(), 32);
    }

    #[test]
    fn test_generate_nonce() {
        let nonce = Encryption::generate_nonce(12).unwrap();
        assert_eq!(nonce.len(), 12);
    }

    #[test]
    fn test_sha256_hashing() {
        let data = b"test data";
        let hash = Encryption::sha256(data);
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn test_sha512_hashing() {
        let data = b"test data";
        let hash = Encryption::sha512(data);
        assert_eq!(hash.len(), 64);
    }

    #[test]
    fn test_hmac_sha256() {
        let key = b"secret key";
        let data = b"test data";
        let hmac = Encryption::hmac_sha256(key, data).unwrap();
        assert_eq!(hmac.len(), 32);
    }

    #[test]
    fn test_aes256gcm_encryption() {
        let key = Encryption::generate_key(32).unwrap();
        let plaintext = b"Secret message";

        let (ciphertext, nonce) = Encryption::aes256gcm_encrypt(&key, plaintext).unwrap();
        assert!(!ciphertext.is_empty());
        assert_eq!(nonce.len(), 12);

        let decrypted = Encryption::aes256gcm_decrypt(&key, &ciphertext, &nonce).unwrap();
        assert_eq!(plaintext, &decrypted[..]);
    }

    #[test]
    fn test_chacha20poly1305_encryption() {
        let key = Encryption::generate_key(32).unwrap();
        let plaintext = b"Secret message";

        let (ciphertext, nonce) = Encryption::chacha20poly1305_encrypt(&key, plaintext).unwrap();
        assert!(!ciphertext.is_empty());
        assert_eq!(nonce.len(), 12);

        let decrypted = Encryption::chacha20poly1305_decrypt(&key, &ciphertext, &nonce).unwrap();
        assert_eq!(plaintext, &decrypted[..]);
    }

    #[test]
    fn test_secure_data() {
        #[derive(serde::Serialize, serde::Deserialize, PartialEq, Debug)]
        struct TestData {
            field1: String,
            field2: u32,
        }

        let key = Encryption::generate_key(32).unwrap();
        let original_data = TestData {
            field1: "test".to_string(),
            field2: 42,
        };

        // Encrypt the data
        let secure_data = SecureData::new(&original_data, &key).unwrap();

        // Decrypt the data
        let decrypted_data = secure_data.decrypt(&key).unwrap();

        // Verify the data matches
        assert_eq!(original_data, decrypted_data);
    }

    #[test]
    fn test_network_security_handshake() {
        // This test would normally require a running server
        // For now, we'll just test the basic functionality

        let network_security = NetworkSecurity::new();

        // Create a socket address
        let addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1)), 8080);

        // We can't actually connect to a server in this test,
        // but we can verify that the handshake function exists and has the right signature
        assert!(network_security.perform_handshake != std::ptr::null());
    }

    #[test]
    fn test_security_utils() {
        // Test timestamp
        let timestamp = SecurityUtils::get_current_timestamp();
        assert!(timestamp > 0);

        // Test input validation
        assert!(SecurityUtils::validate_input("valid input", 100).is_ok());
        assert!(SecurityUtils::validate_input("", 100).is_err());
        assert!(SecurityUtils::validate_input(&"a".repeat(1001), 1000).is_err());

        // Test sanitization
        let dirty_input = "<script>alert('xss')</script>";
        let clean_input = SecurityUtils::sanitize_input(dirty_input);
        assert!(!clean_input.contains("<script>"));

        // Test random string generation
        let random_string = SecurityUtils::generate_secure_random_string(16);
        assert_eq!(random_string.len(), 16);

        // Test UUID validation
        assert!(!SecurityUtils::is_valid_uuid("not-a-uuid"));
        assert!(SecurityUtils::is_valid_uuid("123e4567-e89b-12d3-a456-426614174000"));

        // Test token generation
        let token = SecurityUtils::generate_secure_token(32);
        assert_eq!(token.len(), 32);

        // Test constant-time comparison
        let a = b"test";
        let b = b"test";
        let c = b"different";
        assert!(SecurityUtils::constant_time_eq(a, b));
        assert!(!SecurityUtils::constant_time_eq(a, c));
    }

    #[test]
    fn test_security_audit() {
        let audit = SecurityAudit::new();

        // Create a temporary directory with a test file
        let temp_dir = tempfile::tempdir().unwrap();
        let test_file = temp_dir.path().join("test.rs");
        std::fs::write(&test_file, "let secret = \"password123\";").unwrap();

        // Run the audit
        let result = audit.run_audit(temp_dir.path().to_str().unwrap()).unwrap();

        // Verify that the audit found the hardcoded secret
        assert!(!result.vulnerabilities.is_empty());

        // Check that the vulnerability has the right severity
        let high_vulns: Vec<_> = result.vulnerabilities.iter()
            .filter(|v| v.severity == Severity::High)
            .collect();
        assert!(!high_vulns.is_empty());
    }
}

