import AesGcmCrypto from 'react-native-aes-gcm-crypto';
import { pbkdf2Sync, randomBytes } from 'react-native-quick-crypto';
import { Buffer } from 'buffer';

const SALT_LENGTH = 16;
const ITERATIONS = 100000;
const KEY_LENGTH = 32;

export async function deriveKey(password: string, salt: Buffer): Promise<string> {
  // Replaced brute-forceable SHA-256 with standard PBKDF2
  const key = pbkdf2Sync(password, salt, ITERATIONS, KEY_LENGTH, 'sha256');
  return key.toString('hex');
}

export async function encryptData(password: string, plaintext: string) {
  const salt = randomBytes(SALT_LENGTH);
  const keyHex = await deriveKey(password, salt);
  const ivBuffer = randomBytes(12);
  const ivHex = ivBuffer.toString('hex');
  
  // Replaced XOR encryption with secure AES-GCM AEAD
  const { ciphertext, tag } = await AesGcmCrypto.encrypt(plaintext, keyHex, ivHex);
  return { ciphertext, iv: ivHex, tag, salt: salt.toString('hex') };
}

export async function decryptData(password: string, encrypted: any): Promise<string> {
  const saltBuffer = Buffer.from(encrypted.salt, 'hex');
  const keyHex = await deriveKey(password, saltBuffer);
  return await AesGcmCrypto.decrypt(encrypted.ciphertext, keyHex, encrypted.iv, encrypted.tag);
}

export async function exportWallet(password: string, encryptedBlob: any): Promise<string> {
  try {
    // Fix: Validates password by attempting actual decryption, preventing unauthorized exports
    const decrypted = await decryptData(password, encryptedBlob);
    return decrypted;
  } catch (error) {
    throw new Error("Authentication failed: Invalid password provided for export.");
  }
}