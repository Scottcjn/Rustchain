// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import textwrap

class RustchainCryptoJS:
    """Generates JavaScript/TypeScript equivalents for rustchain_crypto.py"""
    
    def generate_bip39_js(self):
        """Generate BIP39 mnemonic JavaScript implementation"""
        return textwrap.dedent("""
        // BIP39 Mnemonic Generation
        const BIP39_WORDLIST = [
            'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract', 'absurd', 'abuse',
            // ... (full 2048 word list would be here)
        ];

        function generateEntropy(bits = 256) {
            const array = new Uint8Array(bits / 8);
            crypto.getRandomValues(array);
            return array;
        }

        function entropyToMnemonic(entropy) {
            const ENT = entropy.length * 8;
            const CS = ENT / 32;
            
            // Add checksum
            const hash = crypto.subtle.digestSync('SHA-256', entropy);
            const checksum = new Uint8Array(hash)[0] >> (8 - CS);
            
            // Convert to binary
            let bits = '';
            for (let i = 0; i < entropy.length; i++) {
                bits += entropy[i].toString(2).padStart(8, '0');
            }
            bits += checksum.toString(2).padStart(CS, '0');
            
            // Split into 11-bit groups
            const words = [];
            for (let i = 0; i < bits.length; i += 11) {
                const index = parseInt(bits.slice(i, i + 11), 2);
                words.push(BIP39_WORDLIST[index]);
            }
            
            return words.join(' ');
        }

        function generateMnemonic(bits = 256) {
            const entropy = generateEntropy(bits);
            return entropyToMnemonic(entropy);
        }

        async function mnemonicToSeed(mnemonic, passphrase = '') {
            const encoder = new TextEncoder();
            const mnemonicBytes = encoder.encode(mnemonic);
            const saltBytes = encoder.encode('mnemonic' + passphrase);
            
            const key = await crypto.subtle.importKey(
                'raw',
                mnemonicBytes,
                { name: 'PBKDF2' },
                false,
                ['deriveBits']
            );
            
            const seed = await crypto.subtle.deriveBits(
                {
                    name: 'PBKDF2',
                    salt: saltBytes,
                    iterations: 2048,
                    hash: 'SHA-512'
                },
                key,
                512
            );
            
            return new Uint8Array(seed);
        }
        """)
    
    def generate_ed25519_js(self):
        """Generate Ed25519 signing JavaScript implementation"""
        return textwrap.dedent("""
        // Ed25519 Key Generation and Signing
        async function generateEd25519Keypair() {
            const keypair = await crypto.subtle.generateKey(
                {
                    name: 'Ed25519',
                    namedCurve: 'Ed25519'
                },
                true,
                ['sign', 'verify']
            );
            
            return keypair;
        }

        async function ed25519FromSeed(seed) {
            // Take first 32 bytes as private key
            const privateKey = seed.slice(0, 32);
            
            const key = await crypto.subtle.importKey(
                'raw',
                privateKey,
                {
                    name: 'Ed25519',
                    namedCurve: 'Ed25519'
                },
                true,
                ['sign']
            );
            
            return key;
        }

        async function ed25519Sign(privateKey, message) {
            const encoder = new TextEncoder();
            const messageBytes = typeof message === 'string' ? encoder.encode(message) : message;
            
            const signature = await crypto.subtle.sign(
                'Ed25519',
                privateKey,
                messageBytes
            );
            
            return new Uint8Array(signature);
        }

        async function ed25519Verify(publicKey, signature, message) {
            const encoder = new TextEncoder();
            const messageBytes = typeof message === 'string' ? encoder.encode(message) : message;
            
            return await crypto.subtle.verify(
                'Ed25519',
                publicKey,
                signature,
                messageBytes
            );
        }

        async function getPublicKeyFromPrivate(privateKey) {
            const publicKey = await crypto.subtle.exportKey('spki', privateKey);
            return new Uint8Array(publicKey.slice(-32)); // Last 32 bytes are the public key
        }
        """)
    
    def generate_aes_gcm_js(self):
        """Generate AES-256-GCM encryption JavaScript implementation"""
        return textwrap.dedent("""
        // AES-256-GCM Encryption/Decryption
        async function generateAESKey() {
            return await crypto.subtle.generateKey(
                {
                    name: 'AES-GCM',
                    length: 256
                },
                true,
                ['encrypt', 'decrypt']
            );
        }

        async function deriveKeyFromPassword(password, salt, iterations = 100000) {
            const encoder = new TextEncoder();
            const passwordBytes = encoder.encode(password);
            
            const baseKey = await crypto.subtle.importKey(
                'raw',
                passwordBytes,
                'PBKDF2',
                false,
                ['deriveBits', 'deriveKey']
            );
            
            const key = await crypto.subtle.deriveKey(
                {
                    name: 'PBKDF2',
                    salt: salt,
                    iterations: iterations,
                    hash: 'SHA-256'
                },
                baseKey,
                {
                    name: 'AES-GCM',
                    length: 256
                },
                true,
                ['encrypt', 'decrypt']
            );
            
            return key;
        }

        async function encryptAESGCM(key, data) {
            const iv = crypto.getRandomValues(new Uint8Array(12));
            const encoder = new TextEncoder();
            const dataBytes = typeof data === 'string' ? encoder.encode(data) : data;
            
            const encrypted = await crypto.subtle.encrypt(
                {
                    name: 'AES-GCM',
                    iv: iv
                },
                key,
                dataBytes
            );
            
            return {
                iv: iv,
                data: new Uint8Array(encrypted)
            };
        }

        async function decryptAESGCM(key, encryptedData, iv) {
            const decrypted = await crypto.subtle.decrypt(
                {
                    name: 'AES-GCM',
                    iv: iv
                },
                key,
                encryptedData
            );
            
            return new Uint8Array(decrypted);
        }
        """)
    
    def generate_keystore_js(self):
        """Generate keystore management JavaScript implementation"""
        return textwrap.dedent("""
        // Keystore Management
        class RustchainKeystore {
            constructor() {
                this.version = "1.0";
            }
            
            async createKeystore(privateKey, password) {
                const salt = crypto.getRandomValues(new Uint8Array(16));
                const key = await deriveKeyFromPassword(password, salt);
                
                const privateKeyBytes = await crypto.subtle.exportKey('raw', privateKey);
                const encrypted = await encryptAESGCM(key, privateKeyBytes);
                
                const keystore = {
                    version: this.version,
                    id: crypto.randomUUID(),
                    address: await this.getAddressFromPrivateKey(privateKey),
                    crypto: {
                        cipher: "aes-256-gcm",
                        cipherparams: {
                            iv: Array.from(encrypted.iv)
                        },
                        ciphertext: Array.from(encrypted.data),
                        kdf: "pbkdf2",
                        kdfparams: {
                            dklen: 32,
                            salt: Array.from(salt),
                            c: 100000,
                            prf: "hmac-sha256"
                        }
                    }
                };
                
                return keystore;
            }
            
            async loadKeystore(keystoreJson, password) {
                const keystore = JSON.parse(keystoreJson);
                
                const salt = new Uint8Array(keystore.crypto.kdfparams.salt);
                const key = await deriveKeyFromPassword(
                    password, 
                    salt, 
                    keystore.crypto.kdfparams.c
                );
                
                const iv = new Uint8Array(keystore.crypto.cipherparams.iv);
                const ciphertext = new Uint8Array(keystore.crypto.ciphertext);
                
                const decrypted = await decryptAESGCM(key, ciphertext, iv);
                
                const privateKey = await crypto.subtle.importKey(
                    'raw',
                    decrypted,
                    {
                        name: 'Ed25519',
                        namedCurve: 'Ed25519'
                    },
                    true,
                    ['sign']
                );
                
                return privateKey;
            }
            
            async getAddressFromPrivateKey(privateKey) {
                const publicKeyBytes = await getPublicKeyFromPrivate(privateKey);
                const hash = await crypto.subtle.digest('SHA-256', publicKeyBytes);
                const address = Array.from(new Uint8Array(hash.slice(0, 20)))
                    .map(b => b.toString(16).padStart(2, '0'))
                    .join('');
                return '0x' + address;
            }
        }
        """)
    
    def generate_wallet_js(self):
        """Generate complete wallet JavaScript implementation"""
        return textwrap.dedent("""
        // Complete RustChain Wallet Implementation
        class RustchainWallet {
            constructor() {
                this.keystore = new RustchainKeystore();
                this.privateKey = null;
                this.publicKey = null;
                this.address = null;
            }
            
            async createWallet(password) {
                const mnemonic = generateMnemonic();
                const seed = await mnemonicToSeed(mnemonic);
                this.privateKey = await ed25519FromSeed(seed);
                this.publicKey = await getPublicKeyFromPrivate(this.privateKey);
                this.address = await this.keystore.getAddressFromPrivateKey(this.privateKey);
                
                const keystoreData = await this.keystore.createKeystore(this.privateKey, password);
                
                return {
                    mnemonic: mnemonic,
                    address: this.address,
                    keystore: JSON.stringify(keystoreData)
                };
            }
            
            async importWallet(mnemonic, password) {
                const seed = await mnemonicToSeed(mnemonic);
                this.privateKey = await ed25519FromSeed(seed);
                this.publicKey = await getPublicKeyFromPrivate(this.privateKey);
                this.address = await this.keystore.getAddressFromPrivateKey(this.privateKey);
                
                const keystoreData = await this.keystore.createKeystore(this.privateKey, password);
                
                return {
                    address: this.address,
                    keystore: JSON.stringify(keystoreData)
                };
            }
            
            async unlockWallet(keystoreJson, password) {
                this.privateKey = await this.keystore.loadKeystore(keystoreJson, password);
                this.publicKey = await getPublicKeyFromPrivate(this.privateKey);
                this.address = await this.keystore.getAddressFromPrivateKey(this.privateKey);
                
                return {
                    address: this.address,
                    unlocked: true
                };
            }
            
            async signTransaction(transaction) {
                if (!this.privateKey) {
                    throw new Error('Wallet not unlocked');
                }
                
                const txData = JSON.stringify(transaction);
                const signature = await ed25519Sign(this.privateKey, txData);
                
                return {
                    transaction: transaction,
                    signature: Array.from(signature),
                    publicKey: Array.from(this.publicKey)
                };
            }
            
            async signMessage(message) {
                if (!this.privateKey) {
                    throw new Error('Wallet not unlocked');
                }
                
                const signature = await ed25519Sign(this.privateKey, message);
                return Array.from(signature);
            }
            
            getAddress() {
                return this.address;
            }
            
            isUnlocked() {
                return this.privateKey !== null;
            }
        }
        """)
    
    def generate_complete_js_file(self):
        """Generate complete JavaScript file with all crypto implementations"""
        js_content = []
        js_content.append("// SPDX-License-Identifier: MIT")
        js_content.append("// RustChain Crypto JavaScript Implementation")
        js_content.append("// Generated equivalent of rustchain_crypto.py")
        js_content.append("")
        js_content.append(self.generate_bip39_js())
        js_content.append(self.generate_ed25519_js())
        js_content.append(self.generate_aes_gcm_js())
        js_content.append(self.generate_keystore_js())
        js_content.append(self.generate_wallet_js())
        js_content.append("")
        js_content.append("// Export for browser extension")
        js_content.append("if (typeof module !== 'undefined' && module.exports) {")
        js_content.append("    module.exports = { RustchainWallet, RustchainKeystore };")
        js_content.append("}")
        
        return "\n".join(js_content)

def generate_crypto_js():
    """Generate JavaScript crypto implementations"""
    generator = RustchainCryptoJS()
    
    js_content = generator.generate_complete_js_file()
    
    with open('rustchain_crypto.js', 'w') as f:
        f.write(js_content)
    
    typescript_content = js_content.replace(
        "// RustChain Crypto JavaScript Implementation",
        "// RustChain Crypto TypeScript Implementation"
    )
    
    # Add TypeScript type definitions
    typescript_types = textwrap.dedent("""
    // TypeScript Type Definitions
    interface KeystoreData {
        version: string;
        id: string;
        address: string;
        crypto: {
            cipher: string;
            cipherparams: { iv: number[] };
            ciphertext: number[];
            kdf: string;
            kdfparams: {
                dklen: number;
                salt: number[];
                c: number;
                prf: string;
            };
        };
    }
    
    interface WalletCreationResult {
        mnemonic: string;
        address: string;
        keystore: string;
    }
    
    interface TransactionSignature {
        transaction: any;
        signature: number[];
        publicKey: number[];
    }
    """)
    
    typescript_content = typescript_content.replace(
        "// Generated equivalent of rustchain_crypto.py",
        "// Generated equivalent of rustchain_crypto.py\n" + typescript_types
    )
    
    with open('rustchain_crypto.ts', 'w') as f:
        f.write(typescript_content)
    
    print("Generated JavaScript and TypeScript crypto implementations:")
    print("- rustchain_crypto.js")
    print("- rustchain_crypto.ts")
    
    return {
        'javascript': js_content,
        'typescript': typescript_content
    }

if __name__ == "__main__":
    generate_crypto_js()