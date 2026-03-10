/**
 * Jest Setup File
 * 
 * Provides mocks for Expo modules that don't work in Jest environment
 */

// Mock expo-crypto
jest.mock('expo-crypto', () => {
  const nodeCrypto = require('crypto');
  
  return {
    getRandomValues: (array) => {
      // Use Node.js crypto for random values
      const randomBytes = nodeCrypto.randomBytes(array.length);
      for (let i = 0; i < array.length; i++) {
        array[i] = randomBytes[i];
      }
      return array;
    },
    digestStringAsync: async (algorithm, data) => {
      // Use Node.js crypto for hashing
      const hash = nodeCrypto.createHash('sha256');
      hash.update(data, 'hex');
      return hash.digest('hex');
    },
    CryptoDigestAlgorithm: {
      SHA256: 'SHA256',
      SHA512: 'SHA512',
    },
  };
});

// Mock expo-secure-store
jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn(),
  getItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

// Mock expo-local-authentication
jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn(() => Promise.resolve(true)),
  isEnrolledAsync: jest.fn(() => Promise.resolve(true)),
  supportedAuthenticationTypesAsync: jest.fn(() => Promise.resolve([])),
  authenticateAsync: jest.fn(() => Promise.resolve({ success: true })),
  AuthenticationType: {
    FACIAL_RECOGNITION: 1,
    FINGERPRINT: 2,
    IRIS: 3,
  },
}));

// Mock expo-camera
jest.mock('expo-camera', () => ({
  CameraView: jest.requireActual('react-native').View,
  useCameraPermissions: () => [
    { granted: true },
    jest.fn(),
  ],
  BarcodeScanningResult: {},
}));
