// SPDX-License-Identifier: MIT

/**
 * RustChain Crypto Module - Browser-compatible JavaScript implementation
 * Provides BIP39 seed generation, Ed25519 signing, AES-256-GCM encryption, and PBKDF2 key derivation
 */

class RustChainCrypto {
    constructor() {
        this.crypto = window.crypto;
        this.subtle = this.crypto.subtle;
    }

    // BIP39 wordlist (English) - subset for demo, full implementation would include all 2048 words
    BIP39_WORDLIST = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", "absurd", "abuse",
        "access", "accident", "account", "accuse", "achieve", "acid", "acoustic", "acquire", "across", "act",
        "action", "actor", "actress", "actual", "adapt", "add", "addict", "address", "adjust", "admit",
        // ... would include full 2048 word list in production
        "zone", "zoo"
    ];

    /**
     * Generate cryptographically secure random bytes
     */
    generateRandomBytes(length) {
        const bytes = new Uint8Array(length);
        this.crypto.getRandomValues(bytes);
        return bytes;
    }

    /**
     * Generate BIP39 mnemonic seed phrase
     */
    async generateMnemonic(wordCount = 24) {
        const entropyBits = wordCount === 12 ? 128 : wordCount === 24 ? 256 : 128;
        const entropyBytes = entropyBits / 8;

        const entropy = this.generateRandomBytes(entropyBytes);
        const entropyHex = Array.from(entropy).map(b => b.toString(16).padStart(2, '0')).join('');

        // Calculate checksum
        const hashBuffer = await this.subtle.digest('SHA-256', entropy);
        const hashArray = new Uint8Array(hashBuffer);
        const checksumBits = entropyBits / 32;

        // Convert entropy + checksum to binary
        let binaryString = '';
        for (let byte of entropy) {
            binaryString += byte.toString(2).padStart(8, '0');
        }

        // Add checksum bits
        const checksumByte = hashArray[0];
        const checksumBinary = checksumByte.toString(2).padStart(8, '0');
        binaryString += checksumBinary.substring(0, checksumBits);

        // Split into 11-bit groups and map to words
        const words = [];
        for (let i = 0; i < binaryString.length; i += 11) {
            const elevenBits = binaryString.substring(i, i + 11);
            const wordIndex = parseInt(elevenBits, 2);
            words.push(this.BIP39_WORDLIST[wordIndex % this.BIP39_WORDLIST.length]);
        }

        return words.join(' ');
    }

    /**
     * Validate BIP39 mnemonic
     */
    validateMnemonic(mnemonic) {
        const words = mnemonic.trim().split(/\s+/);
        if (words.length !== 12 && words.length !== 24) {
            return false;
        }

        // Check all words are in wordlist
        for (let word of words) {
            if (!this.BIP39_WORDLIST.includes(word.toLowerCase())) {
                return false;
            }
        }

        return true;
    }

    /**
     * Derive seed from mnemonic using PBKDF2
     */
    async mnemonicToSeed(mnemonic, passphrase = '') {
        const mnemonicBuffer = new TextEncoder().encode(mnemonic.normalize('NFKD'));
        const saltBuffer = new TextEncoder().encode('mnemonic' + passphrase.normalize('NFKD'));

        const keyMaterial = await this.subtle.importKey(
            'raw',
            mnemonicBuffer,
            { name: 'PBKDF2' },
            false,
            ['deriveBits']
        );

        const seed = await this.subtle.deriveBits(
            {
                name: 'PBKDF2',
                salt: saltBuffer,
                iterations: 2048,
                hash: 'SHA-512'
            },
            keyMaterial,
            512
        );

        return new Uint8Array(seed);
    }

    /**
     * Generate Ed25519 keypair from seed
     */
    async generateEd25519KeyPair(seed) {
        // Ed25519 uses first 32 bytes of seed
        const privateKeyBytes = seed.slice(0, 32);

        // Import as Ed25519 private key
        const privateKey = await this.subtle.importKey(
            'raw',
            privateKeyBytes,
            {
                name: 'Ed25519',
                namedCurve: 'Ed25519'
            },
            true,
            ['sign']
        );

        // Derive public key
        const publicKey = await this.subtle.importKey(
            'spki',
            await this.deriveEd25519PublicKey(privateKeyBytes),
            {
                name: 'Ed25519',
                namedCurve: 'Ed25519'
            },
            true,
            ['verify']
        );

        return { privateKey, publicKey };
    }

    /**
     * Sign message with Ed25519 private key
     */
    async signMessage(privateKey, message) {
        const messageBytes = typeof message === 'string' ?
            new TextEncoder().encode(message) : message;

        const signature = await this.subtle.sign(
            'Ed25519',
            privateKey,
            messageBytes
        );

        return new Uint8Array(signature);
    }

    /**
     * Verify Ed25519 signature
     */
    async verifySignature(publicKey, signature, message) {
        const messageBytes = typeof message === 'string' ?
            new TextEncoder().encode(message) : message;

        return await this.subtle.verify(
            'Ed25519',
            publicKey,
            signature,
            messageBytes
        );
    }

    /**
     * Encrypt data with AES-256-GCM
     */
    async encryptAES256GCM(data, password) {
        const salt = this.generateRandomBytes(16);
        const iv = this.generateRandomBytes(12);

        // Derive key from password using PBKDF2
        const keyMaterial = await this.subtle.importKey(
            'raw',
            new TextEncoder().encode(password),
            { name: 'PBKDF2' },
            false,
            ['deriveBits', 'deriveKey']
        );

        const key = await this.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: salt,
                iterations: 100000,
                hash: 'SHA-256'
            },
            keyMaterial,
            { name: 'AES-GCM', length: 256 },
            false,
            ['encrypt']
        );

        const plaintext = typeof data === 'string' ?
            new TextEncoder().encode(data) : data;

        const ciphertext = await this.subtle.encrypt(
            {
                name: 'AES-GCM',
                iv: iv
            },
            key,
            plaintext
        );

        // Combine salt + iv + ciphertext
        const result = new Uint8Array(salt.length + iv.length + ciphertext.byteLength);
        result.set(salt, 0);
        result.set(iv, salt.length);
        result.set(new Uint8Array(ciphertext), salt.length + iv.length);

        return result;
    }

    /**
     * Decrypt data with AES-256-GCM
     */
    async decryptAES256GCM(encryptedData, password) {
        const salt = encryptedData.slice(0, 16);
        const iv = encryptedData.slice(16, 28);
        const ciphertext = encryptedData.slice(28);

        // Derive key from password using PBKDF2
        const keyMaterial = await this.subtle.importKey(
            'raw',
            new TextEncoder().encode(password),
            { name: 'PBKDF2' },
            false,
            ['deriveBits', 'deriveKey']
        );

        const key = await this.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: salt,
                iterations: 100000,
                hash: 'SHA-256'
            },
            keyMaterial,
            { name: 'AES-GCM', length: 256 },
            false,
            ['decrypt']
        );

        try {
            const plaintext = await this.subtle.decrypt(
                {
                    name: 'AES-GCM',
                    iv: iv
                },
                key,
                ciphertext
            );

            return new Uint8Array(plaintext);
        } catch (error) {
            throw new Error('Decryption failed - invalid password or corrupted data');
        }
    }

    /**
     * Generate PBKDF2 key derivation
     */
    async deriveKeyPBKDF2(password, salt, iterations = 100000, keyLength = 32) {
        const passwordBuffer = new TextEncoder().encode(password);
        const saltBuffer = typeof salt === 'string' ?
            new TextEncoder().encode(salt) : salt;

        const keyMaterial = await this.subtle.importKey(
            'raw',
            passwordBuffer,
            { name: 'PBKDF2' },
            false,
            ['deriveBits']
        );

        const derivedKey = await this.subtle.deriveBits(
            {
                name: 'PBKDF2',
                salt: saltBuffer,
                iterations: iterations,
                hash: 'SHA-256'
            },
            keyMaterial,
            keyLength * 8
        );

        return new Uint8Array(derivedKey);
    }

    /**
     * Convert bytes to hex string
     */
    bytesToHex(bytes) {
        return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
    }

    /**
     * Convert hex string to bytes
     */
    hexToBytes(hex) {
        const bytes = new Uint8Array(hex.length / 2);
        for (let i = 0; i < hex.length; i += 2) {
            bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
        }
        return bytes;
    }

    /**
     * Helper method to derive Ed25519 public key from private key bytes
     * Note: This is a simplified implementation - production would use proper Ed25519 curve math
     */
    async deriveEd25519PublicKey(privateKeyBytes) {
        // This is a placeholder - real implementation would use Ed25519 curve operations
        // For now, we'll use SHA-256 hash as a stand-in (NOT cryptographically correct)
        const hash = await this.subtle.digest('SHA-256', privateKeyBytes);
        return new Uint8Array(hash);
    }

    /**
     * Create wallet keystore (encrypted private key storage)
     */
    async createKeystore(privateKey, password, address) {
        const keystoreData = {
            address: address,
            crypto: {
                cipher: 'aes-256-gcm',
                kdf: 'pbkdf2',
                kdfparams: {
                    dklen: 32,
                    salt: this.bytesToHex(this.generateRandomBytes(32)),
                    c: 100000,
                    prf: 'hmac-sha256'
                }
            },
            id: this.crypto.randomUUID(),
            version: 3
        };

        // Export private key to raw bytes
        const privateKeyBytes = await this.subtle.exportKey('raw', privateKey);

        // Encrypt private key
        const encryptedKey = await this.encryptAES256GCM(privateKeyBytes, password);
        keystoreData.crypto.ciphertext = this.bytesToHex(encryptedKey);

        return keystoreData;
    }

    /**
     * Load wallet from keystore
     */
    async loadFromKeystore(keystoreData, password) {
        try {
            const ciphertext = this.hexToBytes(keystoreData.crypto.ciphertext);
            const privateKeyBytes = await this.decryptAES256GCM(ciphertext, password);

            const privateKey = await this.subtle.importKey(
                'raw',
                privateKeyBytes,
                { name: 'Ed25519' },
                true,
                ['sign']
            );

            return { privateKey, address: keystoreData.address };
        } catch (error) {
            throw new Error('Failed to decrypt keystore - invalid password');
        }
    }
}

// Export for use in browser extension or web applications
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RustChainCrypto;
} else if (typeof window !== 'undefined') {
    window.RustChainCrypto = RustChainCrypto;
}
