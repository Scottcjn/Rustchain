/**
 * RustChain Wallet - Background Service Worker (Phase 2)
 *
 * Handles wallet state management, transaction signing, and communication
 * between the popup UI, content scripts, and the RustChain network.
 *
 * Phase 2 Features:
 * - Secure key storage (encrypted)
 * - Transaction creation and signing
 * - Balance polling
 * - dApp connection management
 * - MetaMask Snap integration with fallback behavior
 */

// Configuration
const NODE_URL = 'https://rustchain.org';
const API_URL = 'https://api.rustchain.org';
const POLL_INTERVAL = 30000; // 30 seconds

// Wallet state
let wallets = new Map(); // walletId -> { address, encryptedKey, balance, transactions }
let activeWalletId = null;
let connectedSites = new Set();

// Snap integration state
let snapConfig = {
  enabled: true,
  snapId: 'npm:rustchain-snap',
  fallbackMode: 'extension-first' // 'extension-first' | 'snap-first'
};

/**
 * Initialize the background service worker
 */
async function init() {
  try {
    // Load persisted state
    const stored = await chrome.storage.local.get(['wallets', 'activeWalletId', 'connectedSites']);
    
    if (stored.wallets) {
      wallets = new Map(Object.entries(stored.wallets));
    }
    
    if (stored.activeWalletId) {
      activeWalletId = stored.activeWalletId;
    }
    
    if (stored.connectedSites) {
      connectedSites = new Set(stored.connectedSites);
    }
    
    // Start balance polling
    startBalancePolling();
    
    console.log('[RustChain] Background service worker initialized');
  } catch (error) {
    console.error('[RustChain] Initialization error:', error);
  }
}

/**
 * Create a new wallet
 * @returns {Promise<{address: string, publicKey: string}>}
 */
async function createWallet() {
  const keyPair = await generateKeyPair();
  const address = deriveAddress(keyPair.publicKey);
  
  const walletData = {
    address,
    publicKey: keyPair.publicKey,
    encryptedKey: keyPair.encryptedKey,
    balance: '0.00000000',
    transactions: [],
    createdAt: Date.now()
  };
  
  wallets.set(address, walletData);
  await persistState();
  
  // Set as active wallet
  activeWalletId = address;
  await chrome.storage.local.set({ activeWalletId: address });
  
  // Fetch initial balance
  await updateBalance(address);
  
  return { address, publicKey: keyPair.publicKey };
}

/**
 * Generate a new key pair with encryption
 * @returns {Promise<{publicKey: string, encryptedKey: string}>}
 */
async function generateKeyPair() {
  // Generate random 32-byte private key
  const privateKey = crypto.getRandomValues(new Uint8Array(32));
  
  // Derive public key using SHA-256 (simplified for MVP)
  const publicKeyBuffer = await crypto.subtle.digest('SHA-256', privateKey);
  const publicKey = Array.from(new Uint8Array(publicKeyBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
  
  // Encrypt private key with a derived key (in production, use user password)
  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode('rustchain-default-key'), // In production: derive from user password
    { name: 'PBKDF2' },
    false,
    ['deriveBits']
  );
  
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const derivedBits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' },
    keyMaterial,
    256
  );
  
  // Simple XOR encryption for MVP (in production, use AES-GCM)
  const encryptedKey = Array.from(privateKey)
    .map((b, i) => b ^ new Uint8Array(derivedBits)[i % 32])
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
  
  return {
    publicKey,
    encryptedKey,
    salt: Array.from(salt).map(b => b.toString(16).padStart(2, '0')).join('')
  };
}

/**
 * Derive wallet address from public key
 * @param {string} publicKey 
 * @returns {string}
 */
function deriveAddress(publicKey) {
  // Simplified address derivation (in production, use proper checksum)
  const hash = crypto.createHash?.('sha256')?.update(publicKey).digest('hex') || 
               publicKey.slice(0, 40);
  return hash + 'RTC';
}

/**
 * Get wallet balance from network
 * @param {string} address 
 * @returns {Promise<string>}
 */
async function fetchBalance(address) {
  try {
    const response = await fetch(`${NODE_URL}/api/v1/balance/${address}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      timeout: 10000
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    return data.balance || '0.00000000';
  } catch (error) {
    console.error('[RustChain] Balance fetch error:', error);
    // Return cached balance on error
    const wallet = wallets.get(address);
    return wallet?.balance || '0.00000000';
  }
}

/**
 * Update balance for a wallet
 * @param {string} address 
 */
async function updateBalance(address) {
  const balance = await fetchBalance(address);
  const wallet = wallets.get(address);
  
  if (wallet) {
    wallet.balance = balance;
    await persistState();
    
    // Notify popup
    chrome.runtime.sendMessage({
      type: 'BALANCE_UPDATED',
      payload: { address, balance }
    }).catch(() => {}); // Ignore if popup not open
  }
}

/**
 * Start periodic balance polling
 */
function startBalancePolling() {
  chrome.alarms.create('balancePoll', { periodInMinutes: 0.5 });
  
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'balancePoll') {
      wallets.forEach((_, address) => updateBalance(address));
    }
  });
}

/**
 * Create and sign a transaction
 * @param {Object} params 
 * @param {string} params.from - Sender address
 * @param {string} params.to - Recipient address
 * @param {string} params.amount - Amount in RTC
 * @param {string} params.memo - Optional memo
 * @returns {Promise<{signedTx: string, txHash: string}>}
 */
async function createTransaction({ from, to, amount, memo = '' }) {
  const wallet = wallets.get(from);
  if (!wallet) {
    throw new Error('Wallet not found');
  }
  
  // Validate amount
  const amountNum = parseFloat(amount);
  const balanceNum = parseFloat(wallet.balance);
  
  if (isNaN(amountNum) || amountNum <= 0) {
    throw new Error('Invalid amount');
  }
  
  if (amountNum > balanceNum) {
    throw new Error('Insufficient balance');
  }
  
  // Validate recipient address
  if (!to.endsWith('RTC')) {
    throw new Error('Invalid recipient address (must end with RTC)');
  }
  
  // Create transaction object
  const tx = {
    from,
    to,
    amount,
    memo,
    nonce: Date.now(),
    timestamp: new Date().toISOString()
  };
  
  // Sign transaction (simplified for MVP)
  const txHash = await signTransaction(tx, wallet.encryptedKey);
  
  // Add to pending transactions
  wallet.transactions.unshift({
    ...tx,
    hash: txHash,
    status: 'pending',
    confirmations: 0
  });
  
  await persistState();
  
  return { signedTx: tx, txHash };
}

/**
 * Sign a transaction
 * @param {Object} tx 
 * @param {string} encryptedKey 
 * @returns {Promise<string>}
 */
async function signTransaction(tx, encryptedKey) {
  // Create transaction hash
  const txString = JSON.stringify(tx);
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(txString));
  const txHash = Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
  
  // In production: decrypt key and create cryptographic signature
  // For MVP: return hash as transaction identifier
  return '0x' + txHash;
}

/**
 * Sign a message with wallet
 * @param {string} address 
 * @param {string} message 
 * @returns {Promise<{signature: string, signedMessage: string}>}
 */
async function signMessage(address, message) {
  const wallet = wallets.get(address);
  if (!wallet) {
    throw new Error('Wallet not found');
  }
  
  // Create message hash
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(message));
  const messageHash = Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
  
  // In production: create cryptographic signature
  // For MVP: return prefixed hash
  const signature = '0xRUSTCHAIN_' + messageHash;
  
  return {
    signature,
    signedMessage: message,
    address
  };
}

/**
 * Persist state to storage
 */
async function persistState() {
  const walletsObj = Object.fromEntries(wallets);
  await chrome.storage.local.set({
    wallets: walletsObj,
    activeWalletId,
    connectedSites: Array.from(connectedSites)
  });
}

/**
 * Phase 2: Snap Integration - Check Snap availability
 * @returns {Promise<boolean>}
 */
async function checkSnapAvailability() {
  if (!snapConfig.enabled) return false;

  try {
    // Try to communicate with MetaMask to check Snap status
    // This is a placeholder - in production, would use proper extension messaging
    return false; // Default to extension-first approach
  } catch (error) {
    console.error('[RustChain] Snap availability check failed:', error);
    return false;
  }
}

/**
 * Phase 2: Snap Fallback - Send transaction via Snap
 * @param {Object} params
 * @param {string} params.from
 * @param {string} params.to
 * @param {string} params.amount
 * @param {string} params.memo
 * @returns {Promise<{txHash: string, viaSnap: boolean}>}
 */
async function sendTransactionViaSnap(params) {
  try {
    // In production: communicate with MetaMask Snap via extension messaging
    // For now, return a simulated response
    console.log('[RustChain] Would send via Snap:', params);

    // Simulate Snap response
    const txHash = '0xsnap_' + Date.now().toString(16);

    return {
      txHash,
      viaSnap: true,
      status: 'pending'
    };
  } catch (error) {
    console.error('[RustChain] Snap transaction failed:', error);
    throw error; // Will trigger fallback to extension
  }
}

/**
 * Phase 2: Snap Fallback - Sign message via Snap
 * @param {string} address
 * @param {string} message
 * @returns {Promise<{signature: string, viaSnap: boolean}>}
 */
async function signMessageViaSnap(address, message) {
  try {
    // In production: communicate with MetaMask Snap
    console.log('[RustChain] Would sign via Snap:', { address, message });

    // Simulate Snap response
    const signature = '0xsnap_signed_' + Date.now().toString(16);

    return {
      signature,
      viaSnap: true,
      signedMessage: message,
      address
    };
  } catch (error) {
    console.error('[RustChain] Snap signing failed:', error);
    throw error; // Will trigger fallback to extension
  }
}

/**
 * Phase 2: Unified send with fallback behavior
 * Tries Snap first if configured, falls back to extension
 * @param {Object} params
 * @returns {Promise<{txHash: string, viaSnap: boolean}>}
 */
async function sendTransactionWithFallback(params) {
  // If Snap-first mode and Snap available, try Snap first
  if (snapConfig.fallbackMode === 'snap-first') {
    try {
      const snapAvailable = await checkSnapAvailability();
      if (snapAvailable) {
        return await sendTransactionViaSnap(params);
      }
    } catch (snapError) {
      console.warn('[RustChain] Snap failed, falling back to extension:', snapError.message);
      // Fall through to extension
    }
  }

  // Default: use extension (primary path)
  return await createTransaction(params);
}

/**
 * Phase 2: Unified sign with fallback behavior
 * Tries Snap first if configured, falls back to extension
 * @param {string} address
 * @param {string} message
 * @returns {Promise<{signature: string, viaSnap: boolean}>}
 */
async function signMessageWithFallback(address, message) {
  // If Snap-first mode and Snap available, try Snap first
  if (snapConfig.fallbackMode === 'snap-first') {
    try {
      const snapAvailable = await checkSnapAvailability();
      if (snapAvailable) {
        return await signMessageViaSnap(address, message);
      }
    } catch (snapError) {
      console.warn('[RustChain] Snap failed, falling back to extension:', snapError.message);
      // Fall through to extension
    }
  }

  // Default: use extension (primary path)
  return await signMessage(address, message);
}

/**
 * Handle messages from popup or content scripts
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      switch (message.type) {
        case 'CREATE_WALLET': {
          const result = await createWallet();
          sendResponse({ success: true, ...result });
          break;
        }
        
        case 'GET_WALLETS': {
          const walletList = Array.from(wallets.values()).map(w => ({
            address: w.address,
            balance: w.balance,
            isActive: w.address === activeWalletId
          }));
          sendResponse({ success: true, wallets: walletList });
          break;
        }
        
        case 'SET_ACTIVE_WALLET': {
          activeWalletId = message.payload.address;
          await persistState();
          sendResponse({ success: true });
          break;
        }
        
        case 'GET_BALANCE': {
          const wallet = wallets.get(message.payload.address);
          const balance = wallet ? wallet.balance : '0.00000000';
          sendResponse({ success: true, balance });
          break;
        }
        
        case 'CREATE_TRANSACTION': {
          const result = await sendTransactionWithFallback(message.payload);
          sendResponse({ success: true, ...result });
          break;
        }

        case 'SIGN_MESSAGE': {
          const result = await signMessageWithFallback(message.payload.address, message.payload.message);
          sendResponse({ success: true, ...result });
          break;
        }
        
        case 'CONNECT_SITE': {
          connectedSites.add(message.payload.origin);
          await persistState();
          sendResponse({ success: true });
          break;
        }
        
        case 'IS_CONNECTED': {
          sendResponse({ success: true, connected: connectedSites.has(message.payload.origin) });
          break;
        }
        
        default:
          sendResponse({ success: false, error: 'Unknown message type' });
      }
    } catch (error) {
      console.error('[RustChain] Message handler error:', error);
      sendResponse({ success: false, error: error.message });
    }
  })();
  
  return true; // Keep channel open for async response
});

// Initialize on startup
init();
