import Aes from 'react-native-aes-gcm-crypto';
import { Buffer } from 'buffer';

const ITERATIONS = 100000;
const KEY_LENGTH = 32;

export async function generateSalt(): Promise<string> {
    return Buffer.from(await Aes.randomKey(16)).toString('hex');
}

export async function deriveKey(password: string, salt: string): Promise<string> {
    // Replaced single SHA-256 with PBKDF2 for brute-force resistance
    return await Aes.pbkdf2(password, salt, ITERATIONS, KEY_LENGTH, 'sha256');
}

export async function encrypt(data: string, key: string): Promise<{ ciphertext: string, iv: string, tag: string }> {
    // Replaced XOR encryption with AES-GCM AEAD
    const iv = await Aes.randomKey(12);
    const encrypted = await Aes.encrypt(data, key, iv, 'aes-256-gcm');
    return {
        ciphertext: encrypted.ciphertext,
        iv,
        tag: encrypted.tag
    };
}

export async function decrypt(ciphertext: string, key: string, iv: string, tag: string): Promise<string> {
    return await Aes.decrypt(ciphertext, key, iv, tag, 'aes-256-gcm');
}
