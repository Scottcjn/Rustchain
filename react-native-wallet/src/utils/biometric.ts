/**
 * Biometric Authentication Utility
 *
 * Provides FaceID/TouchID/Android biometric authentication
 * with graceful fallback when biometric is unavailable
 */

import * as LocalAuthentication from 'expo-local-authentication';
import { Platform, Alert } from 'react-native';

/**
 * Biometric authentication result
 */
export interface BiometricResult {
  success: boolean;
  error?: string;
  biometricType?: BiometricType;
  available: boolean;
}

/**
 * Available biometric types
 */
export type BiometricType =
  | 'FACE_ID'
  | 'TOUCH_ID'
  | 'IRIS'
  | 'FINGERPRINT'
  | 'FACE'
  | 'NONE';

/**
 * Check if biometric authentication is available
 */
export async function isBiometricAvailable(): Promise<boolean> {
  try {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) return false;

    const isEnrolled = await LocalAuthentication.isEnrolledAsync();
    if (!isEnrolled) return false;

    return true;
  } catch (error) {
    console.error('Biometric availability check failed:', error);
    return false;
  }
}

/**
 * Get the type of biometric authentication available
 */
export async function getBiometricType(): Promise<BiometricType> {
  try {
    const supportedTypes = await LocalAuthentication.supportedAuthenticationTypesAsync();
    
    if (supportedTypes.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      if (Platform.OS === 'ios') {
        return 'FACE_ID';
      }
      return 'FACE';
    }
    
    if (supportedTypes.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      return 'FINGERPRINT';
    }
    
    if (supportedTypes.includes(LocalAuthentication.AuthenticationType.IRIS)) {
      return 'IRIS';
    }

    return 'NONE';
  } catch (error) {
    console.error('Failed to get biometric type:', error);
    return 'NONE';
  }
}

/**
 * Get human-readable name for biometric type
 */
export function getBiometricTypeName(type: BiometricType): string {
  switch (type) {
    case 'FACE_ID':
      return 'Face ID';
    case 'TOUCH_ID':
      return 'Touch ID';
    case 'FINGERPRINT':
      return 'Fingerprint';
    case 'FACE':
      return 'Face Recognition';
    case 'IRIS':
      return 'Iris Scan';
    default:
      return 'Biometric';
  }
}

/**
 * Prompt for biometric authentication
 * 
 * @param promptMessage - Message shown to user
 * @param cancelLabel - Custom cancel button label
 * @param fallbackLabel - Custom fallback button label (use password)
 * @returns BiometricResult with success status
 */
export async function authenticateWithBiometrics(
  promptMessage: string = 'Authenticate to continue',
  cancelLabel: string = 'Cancel',
  fallbackLabel?: string
): Promise<BiometricResult> {
  try {
    // Check availability first
    const available = await isBiometricAvailable();
    if (!available) {
      return {
        success: false,
        error: 'Biometric authentication not available',
        available: false,
      };
    }

    // Get biometric type for display
    const biometricType = await getBiometricType();
    const typeName = getBiometricTypeName(biometricType);

    // Prepare authentication prompt
    const options: LocalAuthentication.LocalAuthenticationOptions = {
      promptMessage,
      cancelLabel,
      fallbackLabel: fallbackLabel || 'Use Password',
      disableDeviceFallback: false, // Allow device PIN/pattern as fallback
    };

    // Attempt authentication
    const result = await LocalAuthentication.authenticateAsync(options);

    if (result.success) {
      return {
        success: true,
        biometricType,
        available: true,
      };
    } else {
      let errorMessage = 'Authentication failed';
      
      if (result.error === 'user_cancel') {
        errorMessage = 'Authentication cancelled';
      } else if (result.error === 'lockout') {
        errorMessage = 'Too many failed attempts. Please try again later.';
      } else if (result.error === 'user_fallback') {
        errorMessage = 'User chose password fallback';
      } else if (result.error === 'system_cancel') {
        errorMessage = 'Authentication cancelled by system';
      }

      return {
        success: false,
        error: errorMessage,
        biometricType,
        available: true,
      };
    }
  } catch (error: any) {
    console.error('Biometric authentication error:', error);
    return {
      success: false,
      error: error.message || 'Authentication failed',
      available: false,
    };
  }
}

/**
 * Authenticate with biometrics or fallback to password
 * 
 * This is the main function to use for sensitive operations.
 * It will:
 * 1. Try biometric authentication if available
 * 2. If not available, return with available: false so app can use password
 * 3. If user cancels biometric, return with error so app can decide next step
 * 
 * @param promptMessage - Message shown in biometric prompt
 * @returns BiometricResult with success status and availability
 */
export async function authenticateWithBiometricsOrFallback(
  promptMessage: string = 'Authenticate to continue'
): Promise<BiometricResult> {
  const available = await isBiometricAvailable();
  
  if (!available) {
    // Biometric not available, app should use password
    return {
      success: false,
      error: 'Biometric authentication not available on this device',
      available: false,
      biometricType: 'NONE',
    };
  }

  // Try biometric authentication
  return authenticateWithBiometrics(promptMessage);
}

/**
 * Show biometric authentication with Alert fallback
 * 
 * Shows a dialog asking user to choose between biometric and password.
 * This provides a graceful UX when biometric might fail or be unavailable.
 * 
 * @param promptMessage - Message for biometric prompt
 * @param onBiometricSuccess - Callback when biometric succeeds
 * @param onPasswordRequested - Callback when user wants to use password
 * @returns Promise resolving to 'biometric' | 'password' | 'cancelled'
 */
export async function showBiometricOrPasswordChoice(
  promptMessage: string = 'Authenticate to continue',
  onBiometricSuccess?: () => void,
  onPasswordRequested?: () => void
): Promise<'biometric' | 'password' | 'cancelled'> {
  const available = await isBiometricAvailable();
  const biometricType = await getBiometricType();
  const typeName = getBiometricTypeName(biometricType);

  if (!available) {
    // No biometric available, go straight to password
    if (onPasswordRequested) onPasswordRequested();
    return 'password';
  }

  return new Promise((resolve) => {
    Alert.alert(
      'Authentication Required',
      promptMessage,
      [
        {
          text: `Use ${typeName}`,
          onPress: async () => {
            const result = await authenticateWithBiometrics(promptMessage);
            if (result.success) {
              if (onBiometricSuccess) onBiometricSuccess();
              resolve('biometric');
            } else {
              // Biometric failed, offer password
              if (onPasswordRequested) onPasswordRequested();
              resolve('password');
            }
          },
        },
        {
          text: 'Use Password',
          onPress: () => {
            if (onPasswordRequested) onPasswordRequested();
            resolve('password');
          },
          style: 'cancel',
        },
      ],
      { cancelable: true }
    );
  });
}

/**
 * Biometric authentication hook-like utility for React components
 * 
 * Usage in component:
 * ```tsx
 * const handleSend = async () => {
 *   const auth = await requireBiometricAuth('Confirm transaction');
 *   if (!auth.success && auth.available) {
 *     // Biometric failed but is available - show error
 *     Alert.alert('Authentication Failed', auth.error);
 *     return;
 *   }
 *   if (!auth.available) {
 *     // Biometric not available - use password flow
 *     setShowPasswordInput(true);
 *     return;
 *   }
 *   // Success - proceed with transaction
 *   proceedWithTransaction();
 * };
 * ```
 */
export async function requireBiometricAuth(
  promptMessage: string = 'Authenticate to continue'
): Promise<BiometricResult> {
  return authenticateWithBiometricsOrFallback(promptMessage);
}

export default {
  isBiometricAvailable,
  getBiometricType,
  getBiometricTypeName,
  authenticateWithBiometrics,
  authenticateWithBiometricsOrFallback,
  showBiometricOrPasswordChoice,
  requireBiometricAuth,
};
