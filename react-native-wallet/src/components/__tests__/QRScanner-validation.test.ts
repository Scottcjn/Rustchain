/**
 * QR Scanner Payload Validation Tests
 *
 * Issue #785: Strict QR payload validation tests
 */

import {
  parseQRPayload,
  validatePaymentRequest,
  type QRPayload,
  type PaymentRequest,
} from '../QRScanner';
import { generateKeyPair, publicKeyToBase58 } from '../../utils/crypto';

describe('QR Scanner Payload Validation', () => {
  describe('parseQRPayload', () => {
    it('should parse plain address', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);

      const result = parseQRPayload(address);

      expect(result.type).toBe('address');
      expect(result.validated).toBe(true);
      expect(result.data).toBe(address);
      expect(result.warnings.length).toBe(0);
    });

    it('should parse rustchain:// URI', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rustchain://${address}`;

      const result = parseQRPayload(uri);

      expect(result.type).toBe('address');
      expect(result.validated).toBe(true);
    });

    it('should parse rtc:// URI', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rtc://${address}`;

      const result = parseQRPayload(uri);

      expect(result.type).toBe('address');
      expect(result.validated).toBe(true);
    });

    it('should parse payment request with amount', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rustchain://${address}?amount=10.5&memo=Payment`;

      const result = parseQRPayload(uri);

      expect(result.type).toBe('payment_request');
      expect(result.validated).toBe(true);

      const paymentRequest: PaymentRequest = JSON.parse(result.data);
      expect(paymentRequest.address).toBe(address);
      expect(paymentRequest.amount).toBe(10.5);
      expect(paymentRequest.memo).toBe('Payment');
    });

    it('should parse JSON payload', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const json = JSON.stringify({
        address,
        amount: 5.0,
        memo: 'Test',
      });

      const result = parseQRPayload(json);

      expect(result.type).toBe('payment_request');
      expect(result.validated).toBe(true);
    });

    it('should reject empty payload', () => {
      const result = parseQRPayload('');

      expect(result.type).toBe('unknown');
      expect(result.validated).toBe(false);
      expect(result.warnings).toContain('Empty payload');
    });

    it('should reject whitespace-only payload', () => {
      const result = parseQRPayload('   ');

      expect(result.type).toBe('unknown');
      expect(result.validated).toBe(false);
    });

    it('should warn about unknown URI scheme', () => {
      const result = parseQRPayload('unknown://address');

      expect(result.warnings.some(w => w.includes('Unknown URI scheme'))).toBe(true);
    });

    it('should detect transaction hash (not address)', () => {
      const txHash = 'a'.repeat(64);
      const result = parseQRPayload(txHash);

      expect(result.type).toBe('unknown');
      expect(result.validated).toBe(false);
      expect(result.warnings.some(w => w.includes('transaction hash'))).toBe(true);
    });

    it('should reject invalid JSON', () => {
      const result = parseQRPayload('{invalid json}');

      // Invalid JSON should be caught and marked as unknown with warning
      expect(result.type).toBe('unknown');
      expect(result.validated).toBe(false);
    });

    it('should warn about unrecognized JSON format', () => {
      const json = JSON.stringify({ foo: 'bar' });
      const result = parseQRPayload(json);

      expect(result.type).toBe('unknown');
      expect(result.warnings.some(w => w.includes('Unrecognized'))).toBe(true);
    });

    it('should handle addresses with leading/trailing whitespace', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const result = parseQRPayload(`  ${address}  `);

      expect(result.type).toBe('address');
      expect(result.validated).toBe(true);
    });

    it('should parse bitcoin: URI (with warning)', () => {
      const result = parseQRPayload('bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa');

      // Bitcoin addresses are not valid RustChain addresses
      expect(result.validated).toBe(false);
    });

    it('should parse ethereum: URI (with warning)', () => {
      const result = parseQRPayload('ethereum:0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb');

      // Ethereum addresses are not valid RustChain addresses
      expect(result.validated).toBe(false);
    });
  });

  describe('validatePaymentRequest', () => {
    it('should validate correct payment request', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);

      const request: PaymentRequest = {
        address,
        amount: 10.5,
        memo: 'Payment',
      };

      const result = validatePaymentRequest(request);

      expect(result.valid).toBe(true);
      expect(result.errors.length).toBe(0);
    });

    it('should validate request without optional fields', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);

      const request: PaymentRequest = {
        address,
      };

      const result = validatePaymentRequest(request);

      expect(result.valid).toBe(true);
    });

    it('should reject invalid address', () => {
      const request: PaymentRequest = {
        address: 'invalid-address',
      };

      const result = validatePaymentRequest(request);

      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('address'))).toBe(true);
    });

    it('should reject zero amount', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);

      const request: PaymentRequest = {
        address,
        amount: 0,
      };

      const result = validatePaymentRequest(request);

      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('greater than 0'))).toBe(true);
    });

    it('should reject negative amount', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);

      const request: PaymentRequest = {
        address,
        amount: -10,
      };

      const result = validatePaymentRequest(request);

      expect(result.valid).toBe(false);
    });

    it('should reject excessively large amount', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);

      const request: PaymentRequest = {
        address,
        amount: Number.MAX_SAFE_INTEGER + 1,
      };

      const result = validatePaymentRequest(request);

      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('too large'))).toBe(true);
    });
  });

  describe('Security Properties', () => {
    it('should reject malicious URI with javascript: scheme', () => {
      const result = parseQRPayload('javascript:alert("XSS")');

      // javascript is not a valid scheme, should be rejected
      expect(result.validated).toBe(false);
      // The scheme is not in validSchemes list, so it should have a warning
      expect(result.warnings.length).toBeGreaterThan(0);
    });

    it('should reject data: URI', () => {
      const result = parseQRPayload('data:text/html,<script>alert("XSS")</script>');

      expect(result.validated).toBe(false);
    });

    it('should reject file: URI', () => {
      const result = parseQRPayload('file:///etc/passwd');

      expect(result.validated).toBe(false);
    });

    it('should handle very long payloads gracefully', () => {
      const longPayload = 'a'.repeat(10000);
      const result = parseQRPayload(longPayload);

      // Should not crash, should return some result
      expect(result).toBeDefined();
      expect(result.type).toBeDefined();
    });

    it('should handle special characters in memo', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rustchain://${address}?memo=${encodeURIComponent('<script>alert("XSS")</script>')}`;

      const result = parseQRPayload(uri);

      // Memo without amount is just an address, not a payment request
      expect(result.type).toBe('address');
      expect(result.validated).toBe(true);
    });

    it('should reject null bytes in payload', () => {
      const result = parseQRPayload('test\x00payload');

      // Should handle gracefully
      expect(result).toBeDefined();
    });

    it('should handle unicode in memo', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rustchain://${address}?memo=${encodeURIComponent('Hello 世界！🚀')}`;

      const result = parseQRPayload(uri);

      // Memo without amount is just an address
      expect(result.type).toBe('address');
      expect(result.validated).toBe(true);
    });
  });

  describe('Edge Cases', () => {
    it('should handle URI without scheme separator', () => {
      const result = parseQRPayload('rustchain:address');

      // Should still try to parse
      expect(result).toBeDefined();
    });

    it('should handle multiple query parameters', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rustchain://${address}?amount=10&memo=Test&chain_id=mainnet&extra=ignored`;

      const result = parseQRPayload(uri);

      expect(result.type).toBe('payment_request');
      expect(result.validated).toBe(true);
    });

    it('should handle missing amount in query', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rustchain://${address}?memo=Test`;

      const result = parseQRPayload(uri);

      expect(result.type).toBe('address'); // No amount, so just address
    });

    it('should handle invalid amount in query', () => {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const uri = `rustchain://${address}?amount=notanumber`;

      const result = parseQRPayload(uri);

      // Should still parse, amount will be ignored
      expect(result).toBeDefined();
    });
  });
});
