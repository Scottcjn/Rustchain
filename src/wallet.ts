import nacl from 'tweetnacl';
import { deriveKey, decrypt } from './secure';

export class Wallet {
    private encryptedBlob: any;
    private salt: string;

    constructor(encryptedBlob: any, salt: string) {
        this.encryptedBlob = encryptedBlob;
        this.salt = salt;
    }

    // Fixed export(): requires password parameter and re-authenticates before returning blob
    public async exportWallet(password: string): Promise<any> {
        if (!password) {
            throw new Error('Password is required for export');
        }
        
        const key = await deriveKey(password, this.salt);
        try {
            // Re-authenticate by verifying AEAD tag through decryption
            const decrypted = await decrypt(
                this.encryptedBlob.ciphertext, 
                key, 
                this.encryptedBlob.iv, 
                this.encryptedBlob.tag
            );
            if (!decrypted) {
                throw new Error('Invalid password');
            }
            return this.encryptedBlob;
        } catch (e) {
            throw new Error('Authentication failed during export');
        }
    }

    // Fixed: Verify fromSecretKey vs fromSeed. 32-byte BIP39 seeds should use fromSeed.
    public static generateKeyPair(seed32Bytes: Uint8Array) {
        if (seed32Bytes.length !== 32) {
            throw new Error('Seed must be exactly 32 bytes');
        }
        return nacl.sign.keyPair.fromSeed(seed32Bytes);
    }
}
