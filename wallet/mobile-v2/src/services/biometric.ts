/**
 * Biometric Authentication Service
 *
 * FaceID / TouchID / Android biometric with graceful fallback.
 */

import * as LocalAuthentication from 'expo-local-authentication';
import { Platform, Alert } from 'react-native';
import type { BiometricResult, BiometricType } from '../types';

export async function isBiometricAvailable(): Promise<boolean> {
  try {
    const hw = await LocalAuthentication.hasHardwareAsync();
    if (!hw) return false;
    return LocalAuthentication.isEnrolledAsync();
  } catch {
    return false;
  }
}

export async function getBiometricType(): Promise<BiometricType> {
  try {
    const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      return Platform.OS === 'ios' ? 'FACE_ID' : 'FACE';
    }
    if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      return 'FINGERPRINT';
    }
    if (types.includes(LocalAuthentication.AuthenticationType.IRIS)) {
      return 'IRIS';
    }
    return 'NONE';
  } catch {
    return 'NONE';
  }
}

export function getBiometricTypeName(type: BiometricType): string {
  const names: Record<BiometricType, string> = {
    FACE_ID: 'Face ID',
    TOUCH_ID: 'Touch ID',
    FINGERPRINT: 'Fingerprint',
    FACE: 'Face Recognition',
    IRIS: 'Iris Scan',
    NONE: 'Biometric',
  };
  return names[type];
}

export async function authenticateWithBiometrics(
  promptMessage = 'Authenticate to continue',
  cancelLabel = 'Cancel',
  fallbackLabel?: string
): Promise<BiometricResult> {
  try {
    const available = await isBiometricAvailable();
    if (!available) {
      return { success: false, error: 'Biometric not available', available: false };
    }

    const biometricType = await getBiometricType();
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage,
      cancelLabel,
      fallbackLabel: fallbackLabel || 'Use Password',
      disableDeviceFallback: false,
    });

    if (result.success) {
      return { success: true, biometricType, available: true };
    }

    const errorMap: Record<string, string> = {
      user_cancel: 'Authentication cancelled',
      lockout: 'Too many failed attempts. Try again later.',
      user_fallback: 'User chose password fallback',
      system_cancel: 'Authentication cancelled by system',
    };

    return {
      success: false,
      error: errorMap[result.error ?? ''] ?? 'Authentication failed',
      biometricType,
      available: true,
    };
  } catch (err: any) {
    return {
      success: false,
      error: err.message || 'Authentication failed',
      available: false,
    };
  }
}

export async function authenticateOrFallback(
  promptMessage = 'Authenticate to continue'
): Promise<BiometricResult> {
  const available = await isBiometricAvailable();
  if (!available) {
    return {
      success: false,
      error: 'Biometric not available on this device',
      available: false,
      biometricType: 'NONE',
    };
  }
  return authenticateWithBiometrics(promptMessage);
}

export async function requireBiometricAuth(
  promptMessage = 'Authenticate to continue'
): Promise<BiometricResult> {
  return authenticateOrFallback(promptMessage);
}
