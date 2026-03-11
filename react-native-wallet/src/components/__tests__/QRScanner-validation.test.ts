/**
 * QR Scanner Payload Validation Tests
 */

import {
  parseQRPayload,
  validatePaymentRequest,
  type PaymentRequest,
} from '../QRScanner';

const RTC_A = `RTC${'a'.repeat(40)}`;

describe('QR Scanner Payload Validation', () => {
  describe('parseQRPayload', () => {
    it('should parse a plain RTC address', () => {
      const result = parseQRPayload(RTC_A);
      expect(result.type).toBe('address');
      expect(result.validated).toBe(true);
      expect(result.data).toBe(RTC_A);
    });

    it('should parse a rustchain payment request', () => {
      const uri = `rustchain://${RTC_A}?amount=10.5&memo=Payment&chain_id=rustchain-mainnet-v2`;
      const result = parseQRPayload(uri);

      expect(result.type).toBe('payment_request');
      expect(result.validated).toBe(true);

      const paymentRequest: PaymentRequest = JSON.parse(result.data);
      expect(paymentRequest.address).toBe(RTC_A);
      expect(paymentRequest.amount).toBe(10.5);
      expect(paymentRequest.chain_id).toBe('rustchain-mainnet-v2');
    });

    it('should reject oversized payloads', () => {
      const result = parseQRPayload('a'.repeat(3000));
      expect(result.validated).toBe(false);
      expect(result.warnings).toContain('Payload is too large');
    });

    it('should reject unsupported URI schemes', () => {
      const result = parseQRPayload('bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa');
      expect(result.validated).toBe(false);
      expect(result.warnings.some((warning) => warning.includes('Unknown URI scheme'))).toBe(true);
    });

    it('should reject control characters in payloads', () => {
      const result = parseQRPayload('RTCabc\x00def');
      expect(result.validated).toBe(false);
    });

    it('should reject malformed JSON payloads', () => {
      const result = parseQRPayload('{invalid json}');
      expect(result.validated).toBe(false);
    });
  });

  describe('validatePaymentRequest', () => {
    it('should validate a correct payment request', () => {
      const request: PaymentRequest = {
        address: RTC_A,
        amount: 1.5,
        memo: 'Payment',
        chain_id: 'rustchain-mainnet-v2',
      };

      expect(validatePaymentRequest(request)).toEqual({
        valid: true,
        errors: [],
      });
    });

    it('should reject invalid RTC addresses', () => {
      const result = validatePaymentRequest({
        address: 'invalid-address',
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((error) => error.includes('Invalid recipient address'))).toBe(true);
    });

    it('should reject invalid chain ids', () => {
      const result = validatePaymentRequest({
        address: RTC_A,
        chain_id: 'bad chain id!',
      });

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid chain_id');
    });

    it('should reject non-finite or zero amounts', () => {
      expect(validatePaymentRequest({ address: RTC_A, amount: 0 }).valid).toBe(false);
      expect(validatePaymentRequest({ address: RTC_A, amount: Number.POSITIVE_INFINITY }).valid).toBe(false);
    });
  });
});
