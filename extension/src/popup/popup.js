/**
 * RustChain Wallet - Popup Script (Phase 2)
 *
 * Handles UI interactions for the wallet popup including:
 * - Wallet creation and selection
 * - Balance display
 * - Send/receive/sign flows with MetaMask Snap fallback
 * - Transaction history
 * - MetaMask Snap detection and integration
 */

// DOM Elements
const walletSelect = document.getElementById('walletSelect');
const newWalletBtn = document.getElementById('newWalletBtn');
const balanceAmount = document.getElementById('balanceAmount');
const balanceUsd = document.getElementById('balanceUsd');
const assetBalance = document.getElementById('assetBalance');
const walletAddress = document.getElementById('walletAddress');
const transactionsList = document.getElementById('transactionsList');

// Modal elements
const sendModal = document.getElementById('sendModal');
const receiveModal = document.getElementById('receiveModal');
const signModal = document.getElementById('signModal');

// Action buttons
const sendBtn = document.getElementById('sendBtn');
const receiveBtn = document.getElementById('receiveBtn');
const signBtn = document.getElementById('signBtn');

// Tab buttons
const tabButtons = document.querySelectorAll('.tab');
const tabPanels = document.querySelectorAll('.tab-panel');

// State
let currentWallet = null;
let wallets = [];
let snapDetected = false;
let snapAvailable = false;
let useSnapFallback = false;

/**
 * Initialize the popup
 */
async function init() {
  await detectMetaMaskSnap();
  await loadWallets();
  setupEventListeners();
  setupTabNavigation();
  setupModalHandlers();

  // Listen for balance updates
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'BALANCE_UPDATED' && message.payload.address === currentWallet?.address) {
      updateBalanceDisplay(message.payload.balance);
    }
  });
}

/**
 * Detect MetaMask Snap availability
 * Phase 2: Snap integration with fallback behavior
 */
async function detectMetaMaskSnap() {
  try {
    // Check if MetaMask is installed
    if (typeof window.ethereum !== 'undefined') {
      try {
        // Check if RustChain Snap is installed
        const snapId = 'npm:rustchain-snap';
        const snapResult = await window.ethereum.request({
          method: 'wallet_getSnaps',
        });

        if (snapResult && snapResult[snapId]) {
          snapDetected = true;
          snapAvailable = true;
          console.log('[RustChain] MetaMask Snap detected:', snapId);
        }
      } catch (e) {
        // Snap not installed or not accessible
        console.log('[RustChain] Snap not available:', e.message);
      }
    }
  } catch (error) {
    console.error('[RustChain] Snap detection error:', error);
  }

  // Determine if we should use Snap fallback
  // Use Snap if: detected AND user prefers it OR extension has no wallets
  useSnapFallback = snapAvailable && wallets.length === 0;
}

/**
 * Check if Snap should be used for operations
 * @returns {boolean}
 */
function shouldUseSnap() {
  return useSnapFallback && snapAvailable;
}

/**
 * Load wallets from background
 */
async function loadWallets() {
  try {
    const response = await sendMessage({ type: 'GET_WALLETS' });
    
    if (response.success) {
      wallets = response.wallets;
      populateWalletSelector();
      
      // Set active wallet
      const activeWallet = wallets.find(w => w.isActive);
      if (activeWallet) {
        currentWallet = activeWallet;
        walletSelect.value = activeWallet.address;
        updateBalanceDisplay(activeWallet.balance);
        walletAddress.textContent = truncateAddress(activeWallet.address);
        assetBalance.textContent = parseFloat(activeWallet.balance).toFixed(8);
        loadTransactions();
      }
    }
  } catch (error) {
    console.error('[RustChain] Load wallets error:', error);
  }
}

/**
 * Populate wallet selector dropdown
 */
function populateWalletSelector() {
  walletSelect.innerHTML = '<option value="">Select Wallet</option>';
  
  wallets.forEach(wallet => {
    const option = document.createElement('option');
    option.value = wallet.address;
    option.textContent = `${truncateAddress(wallet.address)} (${parseFloat(wallet.balance).toFixed(4)} RTC)`;
    walletSelect.appendChild(option);
  });
}

/**
 * Update balance display
 * @param {string} balance 
 */
function updateBalanceDisplay(balance) {
  const balanceNum = parseFloat(balance);
  balanceAmount.textContent = `${balanceNum.toFixed(8)} RTC`;
  balanceUsd.textContent = `≈ $${(balanceNum * 0.01).toFixed(2)} USD`; // Placeholder rate
  assetBalance.textContent = balanceNum.toFixed(8);
}

/**
 * Load transaction history
 */
function loadTransactions() {
  if (!currentWallet) {
    transactionsList.innerHTML = '<div class="empty-state">No transactions yet</div>';
    return;
  }
  
  // In production: fetch from background/network
  // For MVP: show placeholder
  transactionsList.innerHTML = `
    <div class="empty-state">
      <p>Transaction history will appear here</p>
      <p style="font-size: 12px; margin-top: 8px;">Send or receive RTC to see activity</p>
    </div>
  `;
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
  // New wallet button
  newWalletBtn.addEventListener('click', createNewWallet);
  
  // Wallet selector
  walletSelect.addEventListener('change', (e) => {
    const address = e.target.value;
    if (address) {
      selectWallet(address);
    }
  });
  
  // Action buttons
  sendBtn.addEventListener('click', () => openModal(sendModal));
  receiveBtn.addEventListener('click', () => openModal(receiveModal));
  signBtn.addEventListener('click', () => openModal(signModal));
}

/**
 * Setup tab navigation
 */
function setupTabNavigation() {
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const tabId = button.dataset.tab;
      
      // Update active tab
      tabButtons.forEach(b => b.classList.remove('active'));
      button.classList.add('active');
      
      // Show corresponding panel
      tabPanels.forEach(panel => {
        panel.classList.remove('active');
        if (panel.id === `${tabId}Panel`) {
          panel.classList.add('active');
        }
      });
    });
  });
}

/**
 * Setup modal handlers
 */
function setupModalHandlers() {
  // Send modal
  document.getElementById('sendModalClose').addEventListener('click', () => closeModal(sendModal));
  document.getElementById('sendCancel').addEventListener('click', () => closeModal(sendModal));
  document.getElementById('sendConfirm').addEventListener('click', sendTransaction);
  
  // Receive modal
  document.getElementById('receiveModalClose').addEventListener('click', () => closeModal(receiveModal));
  document.getElementById('copyAddress').addEventListener('click', copyAddress);
  
  // Sign modal
  document.getElementById('signModalClose').addEventListener('click', () => closeModal(signModal));
  document.getElementById('signCancel').addEventListener('click', () => closeModal(signModal));
  document.getElementById('signConfirm').addEventListener('click', signMessage);
  
  // Update total when amount changes
  document.getElementById('sendAmount').addEventListener('input', updateSendTotal);
}

/**
 * Create a new wallet
 */
async function createNewWallet() {
  try {
    const response = await sendMessage({ type: 'CREATE_WALLET' });
    
    if (response.success) {
      await loadWallets();
      selectWallet(response.address);
      showNotification('Wallet created successfully!', 'success');
    } else {
      showNotification('Failed to create wallet: ' + response.error, 'error');
    }
  } catch (error) {
    showNotification('Error: ' + error.message, 'error');
  }
}

/**
 * Select a wallet
 * @param {string} address 
 */
async function selectWallet(address) {
  currentWallet = wallets.find(w => w.address === address);
  
  if (currentWallet) {
    await sendMessage({ type: 'SET_ACTIVE_WALLET', payload: { address } });
    updateBalanceDisplay(currentWallet.balance);
    walletAddress.textContent = truncateAddress(currentWallet.address);
    assetBalance.textContent = parseFloat(currentWallet.balance).toFixed(8);
    loadTransactions();
    
    // Update receive modal
    document.getElementById('receiveAddress').value = currentWallet.address;
    drawQRCode(currentWallet.address);
  }
}

/**
 * Send transaction with Snap fallback
 * Phase 2: Integrated send flow with clear fallback behavior
 */
async function sendTransaction() {
  const recipient = document.getElementById('recipientAddress').value.trim();
  const amount = document.getElementById('sendAmount').value;
  const memo = document.getElementById('sendMemo').value.trim();

  if (!recipient || !amount) {
    showNotification('Please fill in all required fields', 'error');
    return;
  }

  // Validate recipient address
  if (!recipient.endsWith('RTC')) {
    showNotification('Invalid recipient address (must end with RTC)', 'error');
    return;
  }

  // Validate amount
  const amountNum = parseFloat(amount);
  if (isNaN(amountNum) || amountNum <= 0) {
    showNotification('Invalid amount', 'error');
    return;
  }

  try {
    // Try Snap first if available (fallback path)
    if (shouldUseSnap() && typeof window.ethereum !== 'undefined') {
      await sendTransactionViaSnap(recipient, amount, memo);
    } else {
      // Use extension's background script (primary path)
      await sendTransactionViaExtension(recipient, amount, memo);
    }
  } catch (error) {
    showNotification('Error: ' + error.message, 'error');
  }
}

/**
 * Send transaction via MetaMask Snap (fallback path)
 * @param {string} recipient
 * @param {string} amount
 * @param {string} memo
 */
async function sendTransactionViaSnap(recipient, amount, memo) {
  try {
    const response = await window.ethereum.request({
      method: 'rustchain_sendTransaction',
      params: [{
        from: currentWallet?.address,
        to: recipient,
        value: amount,
        memo
      }]
    });

    if (response && response.txHash) {
      closeModal(sendModal);
      showNotification('Transaction submitted via Snap! Hash: ' + truncateHash(response.txHash), 'success');

      // Clear form
      document.getElementById('recipientAddress').value = '';
      document.getElementById('sendAmount').value = '';
      document.getElementById('sendMemo').value = '';

      // Refresh wallets
      await loadWallets();
    } else {
      throw new Error('Invalid response from Snap');
    }
  } catch (snapError) {
    console.error('[RustChain] Snap send failed, falling back to extension:', snapError);
    // Fall back to extension
    await sendTransactionViaExtension(recipient, amount, memo);
  }
}

/**
 * Send transaction via extension background (primary path)
 * @param {string} recipient
 * @param {string} amount
 * @param {string} memo
 */
async function sendTransactionViaExtension(recipient, amount, memo) {
  if (!currentWallet) {
    throw new Error('No wallet selected');
  }

  const response = await sendMessage({
    type: 'CREATE_TRANSACTION',
    payload: {
      from: currentWallet.address,
      to: recipient,
      amount,
      memo
    }
  });

  if (response.success) {
    closeModal(sendModal);
    showNotification('Transaction submitted! Hash: ' + truncateHash(response.txHash), 'success');

    // Clear form
    document.getElementById('recipientAddress').value = '';
    document.getElementById('sendAmount').value = '';
    document.getElementById('sendMemo').value = '';

    // Refresh balance
    await loadWallets();
  } else {
    throw new Error(response.error || 'Transaction failed');
  }
}

/**
 * Update send total display
 */
function updateSendTotal() {
  const amount = parseFloat(document.getElementById('sendAmount').value) || 0;
  const fee = 0.0001;
  const total = amount + fee;
  
  document.getElementById('sendTotal').textContent = `${total.toFixed(8)} RTC`;
  document.getElementById('sendBalance').textContent = `${currentWallet?.balance || '0.00000000'} RTC`;
}

/**
 * Copy address to clipboard
 */
async function copyAddress() {
  const addressInput = document.getElementById('receiveAddress');
  
  try {
    await navigator.clipboard.writeText(addressInput.value);
    showNotification('Address copied!', 'success');
  } catch (error) {
    // Fallback
    addressInput.select();
    document.execCommand('copy');
    showNotification('Address copied!', 'success');
  }
}

/**
 * Sign message with Snap fallback
 * Phase 2: Integrated sign flow with clear fallback behavior
 */
async function signMessage() {
  const message = document.getElementById('signMessage').value.trim();

  if (!message) {
    showNotification('Please enter a message to sign', 'error');
    return;
  }

  try {
    // Try Snap first if available (fallback path)
    if (shouldUseSnap() && typeof window.ethereum !== 'undefined') {
      await signMessageViaSnap(message);
    } else {
      // Use extension's background script (primary path)
      await signMessageViaExtension(message);
    }
  } catch (error) {
    showNotification('Error: ' + error.message, 'error');
  }
}

/**
 * Sign message via MetaMask Snap (fallback path)
 * @param {string} message
 */
async function signMessageViaSnap(message) {
  try {
    const response = await window.ethereum.request({
      method: 'rustchain_signMessage',
      params: [{
        address: currentWallet?.address,
        message
      }]
    });

    if (response && response.signature) {
      document.getElementById('signResult').style.display = 'block';
      document.querySelector('#signResult textarea').value = response.signature;
      showNotification('Message signed via Snap!', 'success');
    } else {
      throw new Error('Invalid response from Snap');
    }
  } catch (snapError) {
    console.error('[RustChain] Snap sign failed, falling back to extension:', snapError);
    // Fall back to extension
    await signMessageViaExtension(message);
  }
}

/**
 * Sign message via extension background (primary path)
 * @param {string} message
 */
async function signMessageViaExtension(message) {
  if (!currentWallet) {
    throw new Error('No wallet selected');
  }

  const response = await sendMessage({
    type: 'SIGN_MESSAGE',
    payload: {
      address: currentWallet.address,
      message
    }
  });

  if (response.success) {
    document.getElementById('signResult').style.display = 'block';
    document.querySelector('#signResult textarea').value = response.signature;
    showNotification('Message signed successfully!', 'success');
  } else {
    throw new Error(response.error || 'Signing failed');
  }
}

/**
 * Draw QR code (simplified for MVP)
 * @param {string} address 
 */
function drawQRCode(address) {
  const canvas = document.getElementById('qrCanvas');
  const ctx = canvas.getContext('2d');
  
  // Clear canvas
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  
  // Draw simplified QR-like pattern (in production, use real QR library)
  ctx.fillStyle = '#000000';
  const cellSize = 10;
  const hash = simpleHash(address);
  
  for (let i = 0; i < 20; i++) {
    for (let j = 0; j < 20; j++) {
      if (hash[(i * 20 + j) % hash.length] % 2 === 0) {
        ctx.fillRect(10 + j * cellSize, 10 + i * cellSize, cellSize - 1, cellSize - 1);
      }
    }
  }
  
  // Add corner markers
  ctx.fillStyle = '#000000';
  [[10, 10], [150, 10], [10, 150]].forEach(([x, y]) => {
    ctx.fillRect(x, y, 30, 30);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(x + 6, y + 6, 18, 18);
    ctx.fillStyle = '#000000';
    ctx.fillRect(x + 12, y + 12, 6, 6);
  });
}

/**
 * Simple hash function for QR visualization
 * @param {string} str 
 * @returns {number[]}
 */
function simpleHash(str) {
  const hash = [];
  for (let i = 0; i < str.length; i++) {
    hash.push(str.charCodeAt(i));
  }
  return hash;
}

/**
 * Open modal
 * @param {HTMLElement} modal 
 */
function openModal(modal) {
  if (!currentWallet) {
    showNotification('Please select or create a wallet first', 'error');
    return;
  }
  
  modal.classList.add('active');
  
  // Pre-fill data
  if (modal === receiveModal) {
    document.getElementById('receiveAddress').value = currentWallet.address;
    drawQRCode(currentWallet.address);
  }
  
  if (modal === sendModal) {
    updateSendTotal();
  }
}

/**
 * Close modal
 * @param {HTMLElement} modal 
 */
function closeModal(modal) {
  modal.classList.remove('active');
  
  // Reset sign result
  if (modal === signModal) {
    document.getElementById('signResult').style.display = 'none';
    document.getElementById('signMessage').value = '';
  }
}

/**
 * Send message to background
 * @param {Object} message 
 * @returns {Promise<Object>}
 */
function sendMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

/**
 * Truncate hash for display
 * @param {string} hash
 * @returns {string}
 */
function truncateHash(hash) {
  if (!hash) return '';
  return `${hash.slice(0, 10)}...${hash.slice(-8)}`;
}

/**
 * Truncate address for display
 * @param {string} address
 * @returns {string}
 */
function truncateAddress(address) {
  if (!address) return '';
  return `${address.slice(0, 8)}...${address.slice(-6)}`;
}

/**
 * Show notification
 * @param {string} message 
 * @param {'success' | 'error'} type 
 */
function showNotification(message, type) {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 60px;
    left: 50%;
    transform: translateX(-50%);
    padding: 12px 20px;
    border-radius: 8px;
    background: ${type === 'success' ? '#2ed573' : '#ff4757'};
    color: white;
    font-size: 13px;
    font-weight: 500;
    z-index: 2000;
    animation: slideDown 0.3s ease;
  `;
  
  document.body.appendChild(notification);
  
  // Remove after 3 seconds
  setTimeout(() => {
    notification.style.animation = 'slideUp 0.3s ease';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);
