// SPDX-License-Identifier: MIT

class RustChainWallet {
    constructor() {
        this.baseUrl = 'http://localhost:5000';
        this.walletData = null;
    }

    async createWallet() {
        try {
            const response = await fetch(`${this.baseUrl}/api/wallet/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.walletData = data;
            await this.storeWallet(data);
            return data;
        } catch (error) {
            console.error('Wallet creation failed:', error);
            throw error;
        }
    }

    async importWallet(privateKey, mnemonic = null) {
        try {
            const payload = { private_key: privateKey };
            if (mnemonic) {
                payload.mnemonic = mnemonic;
            }

            const response = await fetch(`${this.baseUrl}/api/wallet/import`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.walletData = data;
            await this.storeWallet(data);
            return data;
        } catch (error) {
            console.error('Wallet import failed:', error);
            throw error;
        }
    }

    async getBalance(address) {
        try {
            const response = await fetch(`${this.baseUrl}/api/wallet/balance/${address}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Balance check failed:', error);
            throw error;
        }
    }

    async signTransaction(transaction) {
        try {
            if (!this.walletData) {
                throw new Error('No wallet loaded');
            }

            const response = await fetch(`${this.baseUrl}/api/wallet/sign`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    transaction: transaction,
                    private_key: this.walletData.private_key
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Transaction signing failed:', error);
            throw error;
        }
    }

    async sendTransaction(to, amount, fee = 0.001) {
        try {
            if (!this.walletData) {
                throw new Error('No wallet loaded');
            }

            const response = await fetch(`${this.baseUrl}/api/wallet/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    from: this.walletData.address,
                    to: to,
                    amount: amount,
                    fee: fee,
                    private_key: this.walletData.private_key
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Transaction failed:', error);
            throw error;
        }
    }

    async storeWallet(walletData) {
        if (typeof chrome !== 'undefined' && chrome.storage) {
            return new Promise((resolve) => {
                chrome.storage.local.set({ rustchain_wallet: walletData }, resolve);
            });
        } else {
            localStorage.setItem('rustchain_wallet', JSON.stringify(walletData));
        }
    }

    async loadWallet() {
        if (typeof chrome !== 'undefined' && chrome.storage) {
            return new Promise((resolve) => {
                chrome.storage.local.get('rustchain_wallet', (result) => {
                    this.walletData = result.rustchain_wallet || null;
                    resolve(this.walletData);
                });
            });
        } else {
            const stored = localStorage.getItem('rustchain_wallet');
            this.walletData = stored ? JSON.parse(stored) : null;
            return this.walletData;
        }
    }

    async clearWallet() {
        this.walletData = null;
        if (typeof chrome !== 'undefined' && chrome.storage) {
            return new Promise((resolve) => {
                chrome.storage.local.remove('rustchain_wallet', resolve);
            });
        } else {
            localStorage.removeItem('rustchain_wallet');
        }
    }

    isWalletLoaded() {
        return this.walletData !== null;
    }

    getWalletAddress() {
        return this.walletData ? this.walletData.address : null;
    }

    async validateAddress(address) {
        try {
            const response = await fetch(`${this.baseUrl}/api/wallet/validate/${address}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Address validation failed:', error);
            return { valid: false };
        }
    }

    async getTransactionHistory(address) {
        try {
            const response = await fetch(`${this.baseUrl}/api/wallet/history/${address}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Transaction history failed:', error);
            throw error;
        }
    }
}

const rustchainWallet = new RustChainWallet();

if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        (async () => {
            try {
                switch (message.action) {
                    case 'create_wallet':
                        const newWallet = await rustchainWallet.createWallet();
                        sendResponse({ success: true, data: newWallet });
                        break;
                    case 'import_wallet':
                        const importedWallet = await rustchainWallet.importWallet(
                            message.privateKey, 
                            message.mnemonic
                        );
                        sendResponse({ success: true, data: importedWallet });
                        break;
                    case 'get_balance':
                        const balance = await rustchainWallet.getBalance(message.address);
                        sendResponse({ success: true, data: balance });
                        break;
                    case 'send_transaction':
                        const txResult = await rustchainWallet.sendTransaction(
                            message.to, 
                            message.amount, 
                            message.fee
                        );
                        sendResponse({ success: true, data: txResult });
                        break;
                    case 'load_wallet':
                        const wallet = await rustchainWallet.loadWallet();
                        sendResponse({ success: true, data: wallet });
                        break;
                    case 'clear_wallet':
                        await rustchainWallet.clearWallet();
                        sendResponse({ success: true });
                        break;
                    default:
                        sendResponse({ success: false, error: 'Unknown action' });
                }
            } catch (error) {
                sendResponse({ success: false, error: error.message });
            }
        })();
        return true;
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = RustChainWallet;
}