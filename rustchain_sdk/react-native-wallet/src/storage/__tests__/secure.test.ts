/**
 * Secure Wallet Storage Tests
 */

import * as SecureStore from 'expo-secure-store';
import { WalletStorage, NonceStore } from '../secure';
import {
  generateKeyPair,
  publicKeyToHex,
  publicKeyToRtcAddress,
  secretKeyToHex,
} from '../../utils/crypto';
import { encryptWithPassword } from '../../utils/aes-gcm';

jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn(),
  getItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

describe('WalletStorage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should save wallets with RTC metadata and AES-GCM encryption', async () => {
    const keyPair = generateKeyPair();
    const address = await publicKeyToRtcAddress(keyPair.publicKey);

    (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);

    const savedAddress = await WalletStorage.save('Test Wallet', keyPair, 'secure_password_123');

    expect(savedAddress).toBe(address);
    const [storageKey, storageValue] = (SecureStore.setItemAsync as jest.Mock).mock.calls[0];
    expect(storageKey).toBe('wallet:Test Wallet');

    const stored = JSON.parse(storageValue);
    expect(stored.metadata.address).toBe(address);
    expect(stored.metadata.publicKeyHex).toBe(publicKeyToHex(keyPair.publicKey));
    expect(stored.encrypted.kdfParams.type).toBe('pbkdf2');
  });

  it('should load wallets after password verification', async () => {
    const keyPair = generateKeyPair();
    const address = await publicKeyToRtcAddress(keyPair.publicKey);
    const password = 'secure_password_123';

    const encrypted = await encryptWithPassword(
      JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      }),
      password,
      'pbkdf2'
    );

    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify({
      metadata: {
        name: 'Test Wallet',
        address,
        publicKeyHex: publicKeyToHex(keyPair.publicKey),
        createdAt: Date.now(),
        network: 'mainnet',
        kdfType: 'pbkdf2',
      },
      encrypted,
      version: 2,
    }));

    const loaded = await WalletStorage.load('Test Wallet', password);
    expect(loaded.publicKey).toEqual(keyPair.publicKey);
    expect(loaded.secretKey).toEqual(keyPair.secretKey);
  });

  it('should export wallets only after re-authentication', async () => {
    const keyPair = generateKeyPair();
    const address = await publicKeyToRtcAddress(keyPair.publicKey);
    const password = 'secure_password_123';

    const encrypted = await encryptWithPassword(
      JSON.stringify({
        secretKey: secretKeyToHex(keyPair.secretKey),
        address,
      }),
      password,
      'pbkdf2'
    );

    const storedJson = JSON.stringify({
      metadata: {
        name: 'Export Wallet',
        address,
        publicKeyHex: publicKeyToHex(keyPair.publicKey),
        createdAt: Date.now(),
        network: 'mainnet',
        kdfType: 'pbkdf2',
      },
      encrypted,
      version: 2,
    });

    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(storedJson);

    await expect(WalletStorage.export('Export Wallet', password)).resolves.toBe(storedJson);
    await expect(WalletStorage.export('Export Wallet', 'wrong_password')).rejects.toThrow();
  });

  it('should normalize legacy metadata when publicKeyHex is available', async () => {
    const keyPair = generateKeyPair();
    const legacyStored = {
      metadata: {
        name: 'Legacy Wallet',
        address: 'legacy-base58-placeholder',
        publicKeyHex: publicKeyToHex(keyPair.publicKey),
        createdAt: Date.now(),
        network: 'mainnet',
        kdfType: 'pbkdf2' as const,
      },
      encrypted: {
        ciphertext: '00',
        iv: '00',
        authTag: '00',
        kdfParams: {
          type: 'pbkdf2' as const,
          salt: '00',
          iterations: 1000,
          dkLen: 32,
        },
      },
      version: 2,
    };

    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(JSON.stringify(legacyStored));
    (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

    const metadata = await WalletStorage.getMetadata('Legacy Wallet');
    expect(metadata?.address).toMatch(/^RTC[0-9a-f]{40}$/);
    expect(SecureStore.setItemAsync).toHaveBeenCalled();
  });
});

describe('NonceStore', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should reserve unique increasing nonces', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValueOnce(null);
    (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

    const first = await NonceStore.reserveNextNonce('RTC' + 'a'.repeat(40), 1000);

    (SecureStore.getItemAsync as jest.Mock).mockResolvedValueOnce(JSON.stringify([first]));
    const second = await NonceStore.reserveNextNonce('RTC' + 'a'.repeat(40), 1000);

    expect(second).toBeGreaterThan(first);
  });

  it('should mark and validate used nonces', async () => {
    (SecureStore.getItemAsync as jest.Mock)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(JSON.stringify([42]));
    (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);

    await NonceStore.markUsed('RTC' + 'b'.repeat(40), 42);
    await expect(NonceStore.validateNonce('RTC' + 'b'.repeat(40), 42)).resolves.toBe(false);
  });
});
