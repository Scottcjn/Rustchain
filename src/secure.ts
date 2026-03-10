import nacl from 'tweetnacl';
import { pbkdf2Sync, randomBytes, createCipheriv, createDecipheriv } from 'crypto';

export interface EncryptedData {
    ciphertext: string;
    iv: string;
    authTag: string;
    salt: string;
}

export class SecureWallet {
    private static readonly ITERATIONS = 250000;
    private static readonly KEY_LENGTH = 32;
    private static readonly DIGEST = 'sha256';

    /**
     * Replace SHA-256 KDF with PBKDF2
     */
    static deriveKey(password: string, salt: Buffer): Buffer {
        return pbkdf2Sync(password, salt, this.ITERATIONS, this.KEY_LENGTH, this.DIGEST);
    }

    /**
     * Replace XOR encryption with AES-GCM
     */
    static encryptData(data: Buffer, password: string): EncryptedData {
        const salt = randomBytes(16);
        const key = this.deriveKey(password, salt);
        const iv = randomBytes(12);

        const cipher = createCipheriv('aes-256-gcm', key, iv);
        let ciphertext = cipher.update(data);
        ciphertext = Buffer.concat([ciphertext, cipher.final()]);
        const authTag = cipher.getAuthTag();

        return {
            ciphertext: ciphertext.toString('base64'),
            iv: iv.toString('base64'),
            authTag: authTag.toString('base64'),
            salt: salt.toString('base64')
        };
    }

    static decryptData(encrypted: EncryptedData, password: string): Buffer {
        const salt = Buffer.from(encrypted.salt, 'base64');
        const key = this.deriveKey(password, salt);
        const iv = Buffer.from(encrypted.iv, 'base64');
        const authTag = Buffer.from(encrypted.authTag, 'base64');

        const decipher = createDecipheriv('aes-256-gcm', key, iv);
        decipher.setAuthTag(authTag);

        let decrypted = decipher.update(Buffer.from(encrypted.ciphertext, 'base64'));
        decrypted = Buffer.concat([decrypted, decipher.final()]);

        return decrypted;
    }

    /**
     * Fix export() function - Require password verification before exporting blob
     */
    static exportWallet(encryptedBlob: EncryptedData, password: string): string {
        if (!password) {
            throw new Error('Authentication required for export');
        }
        try {
            // Verify password by attempting a dry-run decryption
            this.decryptData(encryptedBlob, password);
            return JSON.stringify(encryptedBlob);
        } catch (error) {
            throw new Error('Invalid password. Wallet export aborted.');
        }
    }

    /**
     * Verify fromSecretKey vs fromSeed
     * TweetNaCl fromSecretKey expects 64 bytes, but BIP39 seed is 32 bytes.
     * Fixed to use nacl.sign.keyPair.fromSeed()
     */
    static getKeyPairFromSeed(seed32Bytes: Uint8Array): nacl.SignKeyPair {
        if (seed32Bytes.length !== 32) {
            throw new Error('BIP39 seed must be exactly 32 bytes');
        }
        return nacl.sign.keyPair.fromSeed(seed32Bytes);
    }
}
