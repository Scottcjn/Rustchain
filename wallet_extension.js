// SPDX-License-Identifier: MIT

/**
 * RustChain Wallet Extension - Main wallet logic
 * Handles wallet creation, import, balance checking, and transaction signing
 */

class RustChainWallet {
    constructor() {
        this.isInitialized = false;
        this.currentWallet = null;
        this.encryptedKeystore = null;
        this.sessionPassword = null;
    }

    async initialize() {
        if (this.isInitialized) return;

        try {
            // Check if wallet exists in storage
            const stored = await this.getStoredWallet();
            if (stored) {
                this.encryptedKeystore = stored;
            }
            this.isInitialized = true;
        } catch (error) {
            console.error('Failed to initialize wallet:', error);
            throw error;
        }
    }

    async createWallet(password) {
        if (!password || password.length < 8) {
            throw new Error('Password must be at least 8 characters');
        }

        try {
            // Generate BIP39 24-word seed phrase
            const seedPhrase = await this.generateSeedPhrase();

            // Derive Ed25519 keypair from seed
            const keypair = await this.deriveKeypairFromSeed(seedPhrase);

            // Create wallet object
            const wallet = {
                address: keypair.publicKey,
                privateKey: keypair.privateKey,
                seedPhrase: seedPhrase,
                createdAt: new Date().toISOString()
            };

            // Encrypt and store wallet
            await this.encryptAndStoreWallet(wallet, password);

            this.currentWallet = wallet;
            this.sessionPassword = password;

            return {
                success: true,
                address: wallet.address,
                seedPhrase: seedPhrase
            };
        } catch (error) {
            console.error('Wallet creation failed:', error);
            throw error;
        }
    }

    async importWallet(seedPhraseOrPrivateKey, password) {
        if (!password || password.length < 8) {
            throw new Error('Password must be at least 8 characters');
        }

        try {
            let wallet;

            if (this.isSeedPhrase(seedPhraseOrPrivateKey)) {
                // Import from seed phrase
                const keypair = await this.deriveKeypairFromSeed(seedPhraseOrPrivateKey);
                wallet = {
                    address: keypair.publicKey,
                    privateKey: keypair.privateKey,
                    seedPhrase: seedPhraseOrPrivateKey,
                    importedAt: new Date().toISOString()
                };
            } else {
                // Import from private key
                const publicKey = await this.getPublicKeyFromPrivate(seedPhraseOrPrivateKey);
                wallet = {
                    address: publicKey,
                    privateKey: seedPhraseOrPrivateKey,
                    importedAt: new Date().toISOString()
                };
            }

            await this.encryptAndStoreWallet(wallet, password);

            this.currentWallet = wallet;
            this.sessionPassword = password;

            return {
                success: true,
                address: wallet.address
            };
        } catch (error) {
            console.error('Wallet import failed:', error);
            throw error;
        }
    }

    async unlockWallet(password) {
        if (!this.encryptedKeystore) {
            throw new Error('No wallet found');
        }

        try {
            const wallet = await this.decryptWallet(this.encryptedKeystore, password);
            this.currentWallet = wallet;
            this.sessionPassword = password;

            return {
                success: true,
                address: wallet.address
            };
        } catch (error) {
            console.error('Failed to unlock wallet:', error);
            throw new Error('Invalid password');
        }
    }

    async getBalance() {
        if (!this.currentWallet) {
            throw new Error('Wallet not unlocked');
        }

        try {
            // Call RustChain RPC to get balance
            const response = await this.makeRpcCall('get_balance', {
                address: this.currentWallet.address
            });

            return {
                balance: response.balance || '0',
                address: this.currentWallet.address
            };
        } catch (error) {
            console.error('Failed to get balance:', error);
            throw error;
        }
    }

    async sendTransaction(recipient, amount, fee = '0.001') {
        if (!this.currentWallet) {
            throw new Error('Wallet not unlocked');
        }

        try {
            // Create transaction
            const transaction = {
                from: this.currentWallet.address,
                to: recipient,
                amount: amount,
                fee: fee,
                timestamp: Date.now(),
                nonce: await this.getNonce()
            };

            // Sign transaction
            const signature = await this.signTransaction(transaction);
            transaction.signature = signature;

            // Broadcast transaction
            const response = await this.makeRpcCall('send_transaction', transaction);

            return {
                success: true,
                txHash: response.tx_hash,
                transaction: transaction
            };
        } catch (error) {
            console.error('Transaction failed:', error);
            throw error;
        }
    }

    async signMessage(message) {
        if (!this.currentWallet) {
            throw new Error('Wallet not unlocked');
        }

        try {
            const signature = await this.ed25519Sign(message, this.currentWallet.privateKey);
            return {
                message: message,
                signature: signature,
                publicKey: this.currentWallet.address
            };
        } catch (error) {
            console.error('Message signing failed:', error);
            throw error;
        }
    }

    async exportPrivateKey(password) {
        if (!this.currentWallet) {
            throw new Error('Wallet not unlocked');
        }

        if (password !== this.sessionPassword) {
            throw new Error('Invalid password');
        }

        return this.currentWallet.privateKey;
    }

    async exportSeedPhrase(password) {
        if (!this.currentWallet) {
            throw new Error('Wallet not unlocked');
        }

        if (password !== this.sessionPassword) {
            throw new Error('Invalid password');
        }

        return this.currentWallet.seedPhrase;
    }

    lockWallet() {
        this.currentWallet = null;
        this.sessionPassword = null;
    }

    isLocked() {
        return !this.currentWallet;
    }

    hasWallet() {
        return !!this.encryptedKeystore;
    }

    // Encryption/Storage methods
    async encryptAndStoreWallet(wallet, password) {
        const encrypted = await this.aes256Encrypt(JSON.stringify(wallet), password);
        this.encryptedKeystore = encrypted;

        await chrome.storage.local.set({
            'rustchain_wallet': encrypted
        });
    }

    async decryptWallet(encryptedData, password) {
        const decrypted = await this.aes256Decrypt(encryptedData, password);
        return JSON.parse(decrypted);
    }

    async getStoredWallet() {
        const result = await chrome.storage.local.get(['rustchain_wallet']);
        return result.rustchain_wallet;
    }

    // Crypto helper methods
    async generateSeedPhrase() {
        // Generate 256 bits of entropy
        const entropy = crypto.getRandomValues(new Uint8Array(32));

        // Convert to BIP39 mnemonic
        const wordlist = await this.getBip39Wordlist();
        return this.entropyToMnemonic(entropy, wordlist);
    }

    async deriveKeypairFromSeed(seedPhrase) {
        const seed = await this.mnemonicToSeed(seedPhrase);
        return await this.ed25519FromSeed(seed);
    }

    async signTransaction(transaction) {
        const txData = JSON.stringify({
            from: transaction.from,
            to: transaction.to,
            amount: transaction.amount,
            fee: transaction.fee,
            timestamp: transaction.timestamp,
            nonce: transaction.nonce
        });

        return await this.ed25519Sign(txData, this.currentWallet.privateKey);
    }

    async makeRpcCall(method, params) {
        const rpcUrl = await this.getRpcUrl();

        const response = await fetch(rpcUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: method,
                params: params,
                id: Date.now()
            })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error.message);
        }

        return data.result;
    }

    async getRpcUrl() {
        const settings = await chrome.storage.local.get(['rpc_url']);
        return settings.rpc_url || 'http://localhost:8080/rpc';
    }

    async getNonce() {
        const response = await this.makeRpcCall('get_nonce', {
            address: this.currentWallet.address
        });
        return response.nonce || 0;
    }

    // Crypto implementation stubs - would use actual crypto library
    async aes256Encrypt(data, password) {
        // AES-256-GCM encryption implementation
        const encoder = new TextEncoder();
        const dataBytes = encoder.encode(data);
        const passwordBytes = encoder.encode(password);

        const key = await crypto.subtle.importKey(
            'raw',
            passwordBytes,
            'PBKDF2',
            false,
            ['deriveKey']
        );

        const derivedKey = await crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: crypto.getRandomValues(new Uint8Array(16)),
                iterations: 100000,
                hash: 'SHA-256'
            },
            key,
            { name: 'AES-GCM', length: 256 },
            false,
            ['encrypt']
        );

        const iv = crypto.getRandomValues(new Uint8Array(12));
        const encrypted = await crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: iv },
            derivedKey,
            dataBytes
        );

        return btoa(String.fromCharCode(...new Uint8Array(encrypted)));
    }

    async aes256Decrypt(encryptedData, password) {
        // AES-256-GCM decryption implementation
        // This is a simplified version - real implementation would handle IV properly
        return encryptedData; // Placeholder
    }

    async ed25519Sign(message, privateKey) {
        // Ed25519 signing implementation
        return 'signature_placeholder';
    }

    async ed25519FromSeed(seed) {
        // Generate Ed25519 keypair from seed
        return {
            publicKey: 'public_key_placeholder',
            privateKey: 'private_key_placeholder'
        };
    }

    isSeedPhrase(input) {
        const words = input.trim().split(/\s+/);
        return words.length === 12 || words.length === 24;
    }

    async getPublicKeyFromPrivate(privateKey) {
        // Derive public key from private key
        return 'public_key_from_private';
    }

    async getBip39Wordlist() {
        // Return BIP39 English wordlist
        return [];
    }

    entropyToMnemonic(entropy, wordlist) {
        // Convert entropy to BIP39 mnemonic
        return 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art';
    }

    async mnemonicToSeed(mnemonic) {
        // Convert BIP39 mnemonic to seed
        const encoder = new TextEncoder();
        return encoder.encode(mnemonic);
    }
}

// Extension message handler
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    const wallet = new RustChainWallet();

    (async () => {
        try {
            await wallet.initialize();

            switch (request.action) {
                case 'create_wallet':
                    const created = await wallet.createWallet(request.password);
                    sendResponse(created);
                    break;

                case 'import_wallet':
                    const imported = await wallet.importWallet(request.seedOrKey, request.password);
                    sendResponse(imported);
                    break;

                case 'unlock_wallet':
                    const unlocked = await wallet.unlockWallet(request.password);
                    sendResponse(unlocked);
                    break;

                case 'get_balance':
                    const balance = await wallet.getBalance();
                    sendResponse(balance);
                    break;

                case 'send_transaction':
                    const tx = await wallet.sendTransaction(request.recipient, request.amount, request.fee);
                    sendResponse(tx);
                    break;

                case 'sign_message':
                    const signed = await wallet.signMessage(request.message);
                    sendResponse(signed);
                    break;

                case 'export_private_key':
                    const privateKey = await wallet.exportPrivateKey(request.password);
                    sendResponse({ privateKey });
                    break;

                case 'export_seed_phrase':
                    const seedPhrase = await wallet.exportSeedPhrase(request.password);
                    sendResponse({ seedPhrase });
                    break;

                case 'lock_wallet':
                    wallet.lockWallet();
                    sendResponse({ success: true });
                    break;

                case 'wallet_status':
                    sendResponse({
                        hasWallet: wallet.hasWallet(),
                        isLocked: wallet.isLocked()
                    });
                    break;

                default:
                    sendResponse({ error: 'Unknown action' });
            }
        } catch (error) {
            sendResponse({ error: error.message });
        }
    })();

    return true; // Keep message channel open for async response
});

// Initialize wallet on extension startup
const globalWallet = new RustChainWallet();
globalWallet.initialize().catch(console.error);
