import AesGcmCrypto from 'react-native-aes-gcm-crypto';
import { pbkdf2Sync } from 'react-native-quick-crypto';
import nacl from 'tweetnacl';
import { Buffer } from 'buffer';

const KDF_ITERATIONS = 100000;
const KDF_KEY_LENGTH = 32;

export interface EncryptedWallet {
    ciphertext: string;
    iv: string;
    tag: string;
}

/**
 * CRITICAL: Replace SHA-256 KDF with PBKDF2
 * Prevents brute-force attacks on a single SHA-256 hash.
 */
export function deriveKey(password: string, salt: string): Buffer {
    return pbkdf2Sync(password, salt, KDF_ITERATIONS, KDF_KEY_LENGTH, 'sha256');
}

/**
 * CRITICAL: Replace XOR encryption with AES-GCM
 * Uses secure AEAD encryption for the wallet seed.
 */
export async function encryptSeed(seedPlaintext: string, key: Buffer): Promise<EncryptedWallet> {
    const iv = Buffer.from(nacl.randomBytes(12)).toString('base64');
    const keyBase64 = key.toString('base64');
    
    const { ciphertext, tag } = await AesGcmCrypto.encrypt(
        keyBase64,
        iv,
        seedPlaintext,
        true
    );
    
    return { ciphertext, iv, tag };
}

export async function decryptSeed(encrypted: EncryptedWallet, key: Buffer): Promise<string> {
    const keyBase64 = key.toString('base64');
    return await AesGcmCrypto.decrypt(
        keyBase64,
        encrypted.iv,
        encrypted.ciphertext,
        encrypted.tag,
        true
    );
}

/**
 * CRITICAL: Fix export() function
 * Now requires password parameter to re-authenticate and safely decrypt the blob.
 */
export async function exportWallet(encryptedBlob: EncryptedWallet, salt: string, passwordAttempt: string): Promise<string> {
    if (!passwordAttempt) {
        throw new Error("Password is required for export");
    }
    try {
        const key = deriveKey(passwordAttempt, salt);
        const plaintextSeed = await decryptSeed(encryptedBlob, key);
        if (!plaintextSeed) throw new Error("Decryption returned empty string");
        return plaintextSeed;
    } catch (error) {
        throw new Error("Authentication failed: Invalid password or corrupted data");
    }
}

/**
 * CRITICAL: Verify fromSecretKey vs fromSeed
 * tweetnacl fromSecretKey expects 64 bytes, but simplified BIP39 produces 32.
 * Explicitly uses nacl.sign.keyPair.fromSeed() for 32-byte seeds.
 */
export function getKeyPairFromSeed(seed32Bytes: Uint8Array): nacl.SignKeyPair {
    if (seed32Bytes.length !== 32) {
        throw new Error("Invalid seed length: Expected 32 bytes for ed25519 seed");
    }
    return nacl.sign.keyPair.fromSeed(seed32Bytes);
}
