/**
 * Biometric Authentication Utilities Tests
 */

import {
  isBiometricAvailable,
  getBiometricType,
  getBiometricTypeName,
  authenticateWithBiometrics,
  authenticateWithBiometricsOrFallback,
  requireBiometricAuth,
} from '../biometric';

// Mock expo-local-authentication
jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn(),
  isEnrolledAsync: jest.fn(),
  supportedAuthenticationTypesAsync: jest.fn(),
  authenticateAsync: jest.fn(),
  AuthenticationType: {
    FACIAL_RECOGNITION: 1,
    FINGERPRINT: 2,
    IRIS: 3,
  },
}));

import * as LocalAuthentication from 'expo-local-authentication';

describe('Biometric Authentication Utilities', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('isBiometricAvailable', () => {
    it('should return true when hardware exists and user is enrolled', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);

      const result = await isBiometricAvailable();
      expect(result).toBe(true);
    });

    it('should return false when no hardware exists', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);

      const result = await isBiometricAvailable();
      expect(result).toBe(false);
    });

    it('should return false when user is not enrolled', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(false);

      const result = await isBiometricAvailable();
      expect(result).toBe(false);
    });

    it('should return false when an error occurs', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockRejectedValue(
        new Error('Not available')
      );

      const result = await isBiometricAvailable();
      expect(result).toBe(false);
    });
  });

  describe('getBiometricType', () => {
    it('should return FACE_ID for iOS facial recognition', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockResolvedValue([LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION]);

      const result = await getBiometricType();
      expect(result).toBe('FACE_ID');
    });

    it('should return FINGERPRINT for fingerprint authentication', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockResolvedValue([LocalAuthentication.AuthenticationType.FINGERPRINT]);

      const result = await getBiometricType();
      expect(result).toBe('FINGERPRINT');
    });

    it('should return IRIS for iris scanning', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockResolvedValue([LocalAuthentication.AuthenticationType.IRIS]);

      const result = await getBiometricType();
      expect(result).toBe('IRIS');
    });

    it('should return NONE when no biometric types are supported', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockResolvedValue([]);

      const result = await getBiometricType();
      expect(result).toBe('NONE');
    });

    it('should return NONE when an error occurs', async () => {
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockRejectedValue(new Error('Not available'));

      const result = await getBiometricType();
      expect(result).toBe('NONE');
    });
  });

  describe('getBiometricTypeName', () => {
    it('should return correct name for FACE_ID', () => {
      expect(getBiometricTypeName('FACE_ID')).toBe('Face ID');
    });

    it('should return correct name for TOUCH_ID', () => {
      expect(getBiometricTypeName('TOUCH_ID')).toBe('Touch ID');
    });

    it('should return correct name for FINGERPRINT', () => {
      expect(getBiometricTypeName('FINGERPRINT')).toBe('Fingerprint');
    });

    it('should return correct name for FACE', () => {
      expect(getBiometricTypeName('FACE')).toBe('Face Recognition');
    });

    it('should return correct name for IRIS', () => {
      expect(getBiometricTypeName('IRIS')).toBe('Iris Scan');
    });

    it('should return correct name for NONE', () => {
      expect(getBiometricTypeName('NONE')).toBe('Biometric');
    });
  });

  describe('authenticateWithBiometrics', () => {
    it('should return success result when authentication succeeds', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockResolvedValue([LocalAuthentication.AuthenticationType.FINGERPRINT]);
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: true,
      });

      const result = await authenticateWithBiometrics('Test prompt');
      expect(result.success).toBe(true);
      expect(result.available).toBe(true);
      expect(result.biometricType).toBe('FINGERPRINT');
    });

    it('should return failure when biometric is not available', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

      const result = await authenticateWithBiometrics('Test prompt');
      expect(result.success).toBe(false);
      expect(result.available).toBe(false);
      expect(result.error).toContain('not available');
    });

    it('should return failure when user cancels', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockResolvedValue([LocalAuthentication.AuthenticationType.FINGERPRINT]);
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'user_cancel',
      });

      const result = await authenticateWithBiometrics('Test prompt');
      expect(result.success).toBe(false);
      expect(result.available).toBe(true);
      expect(result.error).toContain('cancelled');
    });

    it('should return failure when too many attempts (lockout)', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock)
        .mockResolvedValue([LocalAuthentication.AuthenticationType.FINGERPRINT]);
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
        error: 'lockout',
      });

      const result = await authenticateWithBiometrics('Test prompt');
      expect(result.success).toBe(false);
      expect(result.available).toBe(true);
      expect(result.error).toContain('Too many failed');
    });
  });

  describe('authenticateWithBiometricsOrFallback', () => {
    it('should return available: false when biometric is not available', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

      const result = await authenticateWithBiometricsOrFallback('Test prompt');
      expect(result.available).toBe(false);
      expect(result.success).toBe(false);
    });

    it('should attempt authentication when biometric is available', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: true,
      });

      const result = await authenticateWithBiometricsOrFallback('Test prompt');
      expect(result.success).toBe(true);
      expect(LocalAuthentication.authenticateAsync).toHaveBeenCalled();
    });
  });

  describe('requireBiometricAuth', () => {
    it('should be an alias for authenticateWithBiometricsOrFallback', async () => {
      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: true,
      });

      const result = await requireBiometricAuth('Test');
      expect(result.success).toBe(true);
    });
  });
});
