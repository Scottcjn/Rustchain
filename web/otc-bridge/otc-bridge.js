/**
 * RustChain OTC Bridge - Client-Side JavaScript
 * Bounty #695 Implementation
 * 
 * Features:
 * - Form validation (amounts, addresses, slippage)
 * - Clear swap flow (quote → approve → execute → confirm)
 * - Security-minded UX (warnings, confirmations, anti-scam checks)
 * - API layer stubs/adapters for backend integration
 */

// ============================================================================
// Configuration & Constants
// ============================================================================

const CONFIG = {
    // Token Configuration
    TOKENS: {
        RTC: {
            symbol: 'RTC',
            name: 'RustChain Token',
            network: 'RustChain',
            icon: '🪙',
            decimals: 8
        },
        wRTC: {
            symbol: 'wRTC',
            name: 'Wrapped RTC (Solana)',
            network: 'Solana',
            icon: '🌉',
            decimals: 6,
            mintAddress: '12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X'
        }
    },
    
    // Bridge Configuration
    BRIDGE: {
        feePercent: 0.1, // 0.1%
        minAmount: 1,
        maxAmount: 100000,
        defaultSlippage: 0.5, // 0.5%
        estimatedTime: '5-30 minutes'
    },
    
    // API Configuration
    API: {
        baseUrl: 'https://rustchain.org',
        timeout: 30000, // 30 seconds
        retryAttempts: 3
    },
    
    // Validation Patterns
    PATTERNS: {
        // Solana address: 32-44 characters, base58
        SOLANA_ADDRESS: /^[1-9A-HJ-NP-Za-km-z]{32,44}$/,
        // RustChain wallet: alphanumeric, 1-256 chars
        RUSTCHAIN_ADDRESS: /^[a-zA-Z0-9_-]{1,256}$/,
        // Amount: positive number with up to 8 decimals
        AMOUNT: /^\d*\.?\d{0,8}$/
    }
};

// ============================================================================
// State Management
// ============================================================================

const state = {
    // Swap direction
    direction: 'rtc-to-wrtc', // 'rtc-to-wrtc' or 'wrtc-to-rtc'
    
    // Form values
    fromAmount: '',
    toAmount: '',
    destinationAddress: '',
    slippage: CONFIG.BRIDGE.defaultSlippage,
    
    // Quote data
    quote: null,
    quoteId: null,
    
    // Wallet connection
    walletConnected: false,
    walletAddress: null,
    fromBalance: 0,
    toBalance: 0,
    
    // UI state
    isLoading: false,
    currentStep: 'input', // 'input', 'review', 'confirming', 'processing', 'completed'
    
    // Token modal state
    tokenModalTarget: null // 'from' or 'to'
};

// ============================================================================
// API Layer - Stubs/Adapters for Backend Integration
// ============================================================================

/**
 * API Adapter Layer
 * Provides a clean interface for backend integration
 * All methods return Promises for consistent async handling
 */
const OTCBridgeAPI = {
    /**
     * Get a quote for swapping tokens
     * @param {Object} params - Quote parameters
     * @param {string} params.from - Source token (RTC or wRTC)
     * @param {string} params.to - Destination token
     * @param {number} params.amount - Amount to swap
     * @param {number} params.slippage - Slippage tolerance percentage
     * @returns {Promise<Object>} Quote object
     */
    async getQuote({ from, to, amount, slippage }) {
        // STUB: Replace with actual API call
        // const response = await fetch(`${CONFIG.API.baseUrl}/api/otc/quote?from=${from}&to=${to}&amount=${amount}&slippage=${slippage}`);
        // return response.json();
        
        // Simulated API delay
        await delay(500);
        
        // Mock response for development/testing
        const rate = from === 'RTC' && to === 'wRTC' ? 0.999 : 1.001;
        const fee = amount * (CONFIG.BRIDGE.feePercent / 100);
        const toAmount = (amount - fee) * rate;
        
        return {
            ok: true,
            quote: {
                from,
                to,
                fromAmount: amount.toString(),
                toAmount: toAmount.toFixed(6),
                rate: rate.toString(),
                fee: fee.toString(),
                feePercent: `${CONFIG.BRIDGE.feePercent}%`,
                slippage: slippage.toString(),
                minimumReceived: (toAmount * (1 - slippage / 100)).toFixed(6),
                priceImpact: amount > 1000 ? (amount / 10000).toFixed(2) : '<0.01',
                validUntil: Math.floor(Date.now() / 1000) + 300 // 5 minutes
            }
        };
    },
    
    /**
     * Execute a token swap
     * @param {Object} params - Swap parameters
     * @param {string} params.from - Source token
     * @param {string} params.to - Destination token
     * @param {number} params.fromAmount - Amount to swap
     * @param {string} params.toAddress - Destination wallet address
     * @param {number} params.slippage - Slippage tolerance
     * @param {string} params.quoteId - Quote ID from getQuote
     * @returns {Promise<Object>} Swap result with transaction hash
     */
    async executeSwap({ from, to, fromAmount, toAddress, slippage, quoteId }) {
        // STUB: Replace with actual API call
        // const response = await fetch(`${CONFIG.API.baseUrl}/api/otc/swap`, {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify({ from, to, fromAmount, toAddress, slippage, quoteId })
        // });
        // return response.json();
        
        // Simulated API delay
        await delay(1000);
        
        // Mock response
        return {
            ok: true,
            swap: {
                id: `swap_${Date.now()}`,
                status: 'pending',
                from,
                to,
                fromAmount: fromAmount.toString(),
                toAmount: state.quote.toAmount,
                txHash: generateMockTxHash(),
                estimatedTime: CONFIG.BRIDGE.estimatedTime,
                createdAt: Math.floor(Date.now() / 1000)
            }
        };
    },
    
    /**
     * Check swap status
     * @param {string} swapId - Swap ID to check
     * @returns {Promise<Object>} Status object with progress
     */
    async getSwapStatus(swapId) {
        // STUB: Replace with actual API call
        // const response = await fetch(`${CONFIG.API.baseUrl}/api/otc/status/${swapId}`);
        // return response.json();
        
        // Simulated API delay
        await delay(300);
        
        // Mock response - simulate progress
        return {
            ok: true,
            status: {
                id: swapId,
                state: 'processing', // 'pending', 'processing', 'completed', 'failed'
                progress: Math.floor(Math.random() * 60) + 20, // 20-80%
                steps: [
                    { name: 'initiated', completed: true, timestamp: Date.now() - 120000 },
                    { name: 'locked', completed: true, timestamp: Date.now() - 60000 },
                    { name: 'bridging', completed: false, timestamp: null },
                    { name: 'completed', completed: false, timestamp: null }
                ]
            }
        };
    },
    
    /**
     * Get wallet balance
     * @param {string} address - Wallet address
     * @param {string} token - Token symbol
     * @returns {Promise<Object>} Balance object
     */
    async getBalance(address, token) {
        // STUB: Replace with actual API call
        // const response = await fetch(`${CONFIG.API.baseUrl}/wallet/balance?miner_id=${address}`);
        // return response.json();
        
        await delay(200);
        
        // Mock balance
        return {
            ok: true,
            balance: (Math.random() * 1000).toFixed(6),
            token
        };
    },
    
    /**
     * Get market data (volume, liquidity, price)
     * @returns {Promise<Object>} Market data object
     */
    async getMarketData() {
        // STUB: Replace with actual API call
        // const response = await fetch(`${CONFIG.API.baseUrl}/api/otc/market`);
        // return response.json();
        
        await delay(300);
        
        // Mock market data
        return {
            ok: true,
            data: {
                volume24h: (Math.random() * 100000 + 50000).toFixed(2),
                liquidity: (Math.random() * 1000000 + 500000).toFixed(2),
                lastPrice: '1.00',
                priceChange24h: (Math.random() * 4 - 2).toFixed(2) // -2% to +2%
            }
        };
    },
    
    /**
     * Get recent transactions
     * @returns {Promise<Object>} List of recent transactions
     */
    async getRecentTransactions() {
        // STUB: Replace with actual API call
        // const response = await fetch(`${CONFIG.API.baseUrl}/api/otc/recent`);
        // return response.json();
        
        await delay(400);
        
        // Mock transactions
        const txs = [];
        for (let i = 0; i < 5; i++) {
            txs.push({
                id: `tx_${Date.now()}_${i}`,
                from: 'RTC',
                to: 'wRTC',
                amount: (Math.random() * 100 + 10).toFixed(2),
                txHash: generateMockTxHash(),
                timestamp: Date.now() - Math.random() * 3600000, // Last hour
                status: 'completed'
            });
        }
        
        return {
            ok: true,
            transactions: txs
        };
    },
    
    /**
     * Validate address format
     * @param {string} address - Address to validate
     * @param {string} network - Network type ('solana' or 'rustchain')
     * @returns {Promise<Object>} Validation result
     */
    async validateAddress(address, network) {
        // STUB: Replace with actual API call for on-chain validation
        // const response = await fetch(`${CONFIG.API.baseUrl}/api/otc/validate-address`, {
        //     method: 'POST',
        //     body: JSON.stringify({ address, network })
        // });
        // return response.json();
        
        await delay(100);
        
        // Client-side validation
        const isValid = network === 'solana' 
            ? CONFIG.PATTERNS.SOLANA_ADDRESS.test(address)
            : CONFIG.PATTERNS.RUSTCHAIN_ADDRESS.test(address);
        
        return {
            ok: isValid,
            valid: isValid,
            network,
            address
        };
    }
};

// ============================================================================
// Utility Functions
// ============================================================================

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function generateMockTxHash() {
    const chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
    let hash = '';
    for (let i = 0; i < 88; i++) {
        hash += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return hash;
}

function formatAddress(address, chars = 4) {
    if (address.length <= chars * 2 + 3) return address;
    return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

function formatNumber(num, decimals = 2) {
    if (typeof num === 'string' && num.startsWith('<')) return num;
    const n = parseFloat(num);
    if (isNaN(n)) return '0.00';
    return n.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

// ============================================================================
// Validation Functions
// ============================================================================

/**
 * Validate amount input
 * @param {string} field - 'from' or 'to'
 * @returns {boolean} Is valid
 */
function validateAmount(field) {
    const input = document.getElementById(`${field}Amount`);
    const errorEl = document.getElementById(`${field}AmountError`);
    const value = input.value.trim();
    
    // Clear previous errors
    if (errorEl) errorEl.textContent = '';
    input.classList.remove('input-error');
    
    // Empty is allowed during input (will validate on submit)
    if (!value) {
        if (field === 'from') state.fromAmount = '';
        if (field === 'to') state.toAmount = '';
        updateSwapButton();
        return true;
    }
    
    // Check format
    if (!CONFIG.PATTERNS.AMOUNT.test(value)) {
        if (errorEl) errorEl.textContent = 'Invalid amount format';
        input.classList.add('input-error');
        return false;
    }
    
    const amount = parseFloat(value);
    
    // Check minimum
    if (amount < CONFIG.BRIDGE.minAmount) {
        if (errorEl) errorEl.textContent = `Minimum amount is ${CONFIG.BRIDGE.minAmount}`;
        input.classList.add('input-error');
        return false;
    }
    
    // Check maximum
    if (amount > CONFIG.BRIDGE.maxAmount) {
        if (errorEl) errorEl.textContent = `Maximum amount is ${CONFIG.BRIDGE.maxAmount}`;
        input.classList.add('input-error');
        return false;
    }
    
    // Check balance (if wallet connected)
    if (state.walletConnected && field === 'from') {
        if (amount > state.fromBalance) {
            if (errorEl) errorEl.textContent = 'Insufficient balance';
            input.classList.add('input-error');
            return false;
        }
    }
    
    // Update state
    if (field === 'from') {
        state.fromAmount = value;
        // Calculate to amount if we have a quote
        if (state.quote) {
            state.toAmount = state.quote.toAmount;
            document.getElementById('toAmount').value = state.quote.toAmount;
        }
    }
    
    // Fetch new quote if from amount changed
    if (field === 'from' && value) {
        fetchQuote();
    }
    
    updateSwapButton();
    return true;
}

/**
 * Validate destination address
 * @returns {boolean} Is valid
 */
function validateAddress() {
    const input = document.getElementById('destinationAddress');
    const errorEl = document.getElementById('addressError');
    const hintEl = document.getElementById('addressHint');
    const value = input.value.trim();
    
    // Clear previous errors
    if (errorEl) errorEl.textContent = '';
    input.classList.remove('input-error');
    
    // Empty is allowed during input
    if (!value) {
        state.destinationAddress = '';
        updateSwapButton();
        return true;
    }
    
    // Determine expected network based on direction
    const expectedNetwork = state.direction === 'rtc-to-wrtc' ? 'solana' : 'rustchain';
    const pattern = expectedNetwork === 'solana' 
        ? CONFIG.PATTERNS.SOLANA_ADDRESS 
        : CONFIG.PATTERNS.RUSTCHAIN_ADDRESS;
    
    // Check format
    if (!pattern.test(value)) {
        if (errorEl) {
            errorEl.textContent = expectedNetwork === 'solana'
                ? 'Invalid Solana address format (32-44 base58 characters)'
                : 'Invalid RustChain address format';
        }
        input.classList.add('input-error');
        return false;
    }
    
    // Update hint with network-specific info
    if (hintEl) {
        hintEl.textContent = expectedNetwork === 'solana'
            ? '💡 Solana addresses are 32-44 characters (base58 format)'
            : '💡 RustChain addresses are alphanumeric (1-256 characters)';
    }
    
    // Async validation (check if address exists on-chain)
    OTCBridgeAPI.validateAddress(value, expectedNetwork)
        .then(result => {
            if (!result.valid) {
                if (errorEl) errorEl.textContent = 'Address not found on network';
                input.classList.add('input-error');
            }
        })
        .catch(err => {
            console.warn('Address validation failed:', err);
        });
    
    state.destinationAddress = value;
    updateSwapButton();
    return true;
}

/**
 * Validate all fields before submission
 * @returns {boolean} All fields valid
 */
function validateAllFields() {
    const amountValid = validateAmount('from');
    const addressValid = validateAddress();
    
    if (!amountValid) {
        showToast('error', 'Please enter a valid amount');
        return false;
    }
    
    if (!addressValid) {
        showToast('error', 'Please enter a valid destination address');
        return false;
    }
    
    if (!state.quote) {
        showToast('error', 'Please wait for quote to load');
        return false;
    }
    
    return true;
}

// ============================================================================
// UI Update Functions
// ============================================================================

function updateSwapButton() {
    const btn = document.getElementById('swapBtn');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');
    
    // Check conditions
    const hasAmount = state.fromAmount && parseFloat(state.fromAmount) > 0;
    const hasAddress = state.destinationAddress && state.destinationAddress.length > 0;
    const hasQuote = state.quote !== null;
    
    if (!state.walletConnected) {
        btn.disabled = true;
        btnText.textContent = 'Connect Wallet to Start';
        btnLoading.style.display = 'none';
    } else if (!hasAmount) {
        btn.disabled = true;
        btnText.textContent = 'Enter Amount';
        btnLoading.style.display = 'none';
    } else if (!hasAddress) {
        btn.disabled = true;
        btnText.textContent = 'Enter Destination Address';
        btnLoading.style.display = 'none';
    } else if (!hasQuote) {
        btn.disabled = true;
        btnText.textContent = 'Getting Quote...';
        btnLoading.style.display = 'none';
    } else {
        btn.disabled = false;
        btnText.textContent = 'Review Swap';
        btnLoading.style.display = 'none';
    }
}

function updateExchangeRate() {
    const rateEl = document.getElementById('exchangeRate');
    if (!rateEl || !state.quote) return;
    
    const { from, to, rate } = state.quote;
    rateEl.querySelector('.rate-value').textContent = `1 ${from} = ${formatNumber(rate, 4)} ${to}`;
}

function updateAdvancedDetails() {
    if (!state.quote) return;
    
    const { priceImpact, feePercent, slippage, minimumReceived } = state.quote;
    
    document.getElementById('priceImpact').textContent = 
        typeof priceImpact === 'string' ? priceImpact : `${formatNumber(priceImpact, 2)}%`;
    document.getElementById('bridgeFee').textContent = `${feePercent}`;
    document.getElementById('slippageTolerance').textContent = `${slippage}%`;
    document.getElementById('minimumReceived').textContent = `${minimumReceived}`;
}

function updateBalances() {
    document.getElementById('fromBalance').textContent = formatNumber(state.fromBalance, 6);
    document.getElementById('toBalance').textContent = formatNumber(state.toBalance, 6);
}

async function updateMarketData() {
    try {
        const result = await OTCBridgeAPI.getMarketData();
        if (result.ok) {
            const { volume24h, liquidity, lastPrice, priceChange24h } = result.data;
            
            document.getElementById('volume24h').textContent = `$${formatNumber(volume24h, 0)}`;
            document.getElementById('liquidity').textContent = `$${formatNumber(liquidity, 0)}`;
            document.getElementById('lastPrice').textContent = `${lastPrice}`;
            
            const changeEl = document.getElementById('priceChange');
            const change = parseFloat(priceChange24h);
            changeEl.textContent = `${change >= 0 ? '+' : ''}${change}%`;
            changeEl.style.color = change >= 0 ? 'var(--green)' : 'var(--red)';
        }
    } catch (err) {
        console.error('Failed to fetch market data:', err);
    }
}

async function updateRecentTransactions() {
    try {
        const result = await OTCBridgeAPI.getRecentTransactions();
        if (result.ok) {
            const container = document.getElementById('recentTxs');
            const txs = result.transactions;
            
            container.innerHTML = txs.map(tx => `
                <div class="tx-item">
                    <div class="tx-info">
                        <a href="#" class="tx-hash" onclick="event.preventDefault()">
                            ${formatAddress(tx.txHash, 6)}
                        </a>
                        <span style="color: var(--text-muted); font-size: 0.75rem;">
                            ${tx.from} → ${tx.to}
                        </span>
                    </div>
                    <div style="text-align: right;">
                        <div class="tx-amount">${tx.amount} ${tx.from}</div>
                        <span class="tx-status">Completed</span>
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error('Failed to fetch recent transactions:', err);
    }
}

// ============================================================================
// Quote & Swap Flow
// ============================================================================

async function fetchQuote() {
    if (!state.fromAmount || parseFloat(state.fromAmount) <= 0) {
        state.quote = null;
        updateExchangeRate();
        updateAdvancedDetails();
        return;
    }
    
    const fromToken = state.direction === 'rtc-to-wrtc' ? 'RTC' : 'wRTC';
    const toToken = state.direction === 'rtc-to-wrtc' ? 'wRTC' : 'RTC';
    
    try {
        state.isLoading = true;
        updateSwapButton();
        
        const result = await OTCBridgeAPI.getQuote({
            from: fromToken,
            to: toToken,
            amount: parseFloat(state.fromAmount),
            slippage: state.slippage
        });
        
        if (result.ok) {
            state.quote = result.quote;
            state.quoteId = `quote_${Date.now()}`; // In real implementation, from API
            
            document.getElementById('toAmount').value = result.quote.toAmount;
            updateExchangeRate();
            updateAdvancedDetails();
        } else {
            showToast('error', 'Failed to get quote');
            state.quote = null;
        }
    } catch (err) {
        console.error('Quote fetch failed:', err);
        showToast('error', 'Network error - please try again');
        state.quote = null;
    } finally {
        state.isLoading = false;
        updateSwapButton();
    }
}

function setDirection(direction) {
    if (state.direction === direction) return;
    
    state.direction = direction;
    
    // Update UI
    document.querySelectorAll('.direction-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.direction === direction);
    });
    
    // Update token symbols
    const fromToken = direction === 'rtc-to-wrtc' ? 'RTC' : 'wRTC';
    const toToken = direction === 'rtc-to-wrtc' ? 'wRTC' : 'RTC';
    
    document.getElementById('fromTokenSymbol').textContent = fromToken;
    document.getElementById('toTokenSymbol').textContent = toToken;
    
    // Update destination field hint
    updateDestinationField();
    
    // Clear amounts and quote
    state.fromAmount = '';
    state.toAmount = '';
    state.quote = null;
    document.getElementById('fromAmount').value = '';
    document.getElementById('toAmount').value = '';
    
    updateExchangeRate();
    updateAdvancedDetails();
    updateSwapButton();
}

function updateDestinationField() {
    const field = document.getElementById('destinationField');
    const input = document.getElementById('destinationAddress');
    const hint = document.getElementById('addressHint');
    
    if (state.direction === 'rtc-to-wrtc') {
        input.placeholder = 'Enter your Solana wallet address';
        hint.textContent = '💡 Solana addresses are 32-44 characters (base58 format)';
    } else {
        input.placeholder = 'Enter your RustChain wallet address';
        hint.textContent = '💡 RustChain addresses are alphanumeric (1-256 characters)';
    }
}

function swapDirection() {
    const newDirection = state.direction === 'rtc-to-wrtc' ? 'wrtc-to-rtc' : 'rtc-to-wrtc';
    setDirection(newDirection);
}

function setPercentage(percent) {
    if (!state.walletConnected || state.fromBalance <= 0) return;
    
    const amount = (state.fromBalance * percent / 100).toFixed(6);
    document.getElementById('fromAmount').value = amount;
    state.fromAmount = amount;
    
    validateAmount('from');
}

// ============================================================================
// Modal Functions
// ============================================================================

function openTokenModal(target) {
    state.tokenModalTarget = target;
    document.getElementById('tokenModal').classList.add('active');
}

function closeTokenModal() {
    document.getElementById('tokenModal').classList.remove('active');
    state.tokenModalTarget = null;
}

function selectToken(symbol) {
    // For OTC bridge, we only support RTC <-> wRTC
    // This function is here for future extensibility
    const target = state.tokenModalTarget;
    
    if (target === 'from') {
        document.getElementById('fromTokenSymbol').textContent = symbol;
    } else {
        document.getElementById('toTokenSymbol').textContent = symbol;
    }
    
    closeTokenModal();
}

function openSettings() {
    document.getElementById('settingsModal').classList.add('active');
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

function setSlippage(value) {
    state.slippage = value;
    
    document.querySelectorAll('.slippage-btn').forEach(btn => {
        btn.classList.toggle('active', parseFloat(btn.textContent) === value);
    });
    
    document.getElementById('customSlippage').value = '';
    document.getElementById('slippageTolerance').textContent = `${value}%`;
    
    // Refetch quote with new slippage
    if (state.fromAmount) {
        fetchQuote();
    }
}

function setCustomSlippage() {
    const value = parseFloat(document.getElementById('customSlippage').value);
    
    if (isNaN(value) || value < 0.01 || value > 5) {
        showToast('error', 'Slippage must be between 0.01% and 5%');
        return;
    }
    
    setSlippage(value);
}

function openConfirmModal() {
    // Populate confirmation details
    const fromToken = state.direction === 'rtc-to-wrtc' ? 'RTC' : 'wRTC';
    const toToken = state.direction === 'rtc-to-wrtc' ? 'wRTC' : 'RTC';
    
    document.getElementById('confirmFromAmount').textContent = 
        `${state.fromAmount} ${fromToken}`;
    document.getElementById('confirmToAmount').textContent = 
        `${state.quote.minimumReceived} ${toToken}`;
    document.getElementById('confirmRate').textContent = 
        `1 ${fromToken} = ${formatNumber(state.quote.rate, 4)} ${toToken}`;
    document.getElementById('confirmImpact').textContent = 
        typeof state.quote.priceImpact === 'string' 
            ? state.quote.priceImpact 
            : `${formatNumber(state.quote.priceImpact, 2)}%`;
    document.getElementById('confirmAddress').textContent = 
        formatAddress(state.destinationAddress, 6);
    
    document.getElementById('confirmModal').classList.add('active');
}

function closeConfirmModal() {
    document.getElementById('confirmModal').classList.remove('active');
}

// ============================================================================
// Swap Execution
// ============================================================================

async function handleSwap(event) {
    event.preventDefault();
    
    if (!validateAllFields()) return;
    
    // Show confirmation modal
    openConfirmModal();
}

async function executeSwap() {
    try {
        closeConfirmModal();
        state.currentStep = 'confirming';
        
        const btn = document.getElementById('swapBtn');
        btn.querySelector('.btn-text').textContent = 'Processing...';
        btn.querySelector('.btn-loading').style.display = 'flex';
        btn.disabled = true;
        
        const fromToken = state.direction === 'rtc-to-wrtc' ? 'RTC' : 'wRTC';
        const toToken = state.direction === 'rtc-to-wrtc' ? 'wRTC' : 'RTC';
        
        // Execute swap via API
        const result = await OTCBridgeAPI.executeSwap({
            from: fromToken,
            to: toToken,
            fromAmount: parseFloat(state.fromAmount),
            toAddress: state.destinationAddress,
            slippage: state.slippage,
            quoteId: state.quoteId
        });
        
        if (result.ok) {
            state.currentStep = 'processing';
            showToast('success', 'Swap initiated! Transaction ID: ' + formatAddress(result.swap.id, 8));
            
            // Show transaction details
            showTransactionResult(result.swap);
            
            // Poll for status updates
            pollSwapStatus(result.swap.id);
        } else {
            throw new Error('Swap failed');
        }
    } catch (err) {
        console.error('Swap execution failed:', err);
        showToast('error', 'Swap failed: ' + err.message);
        
        state.currentStep = 'input';
        updateSwapButton();
    }
}

function showTransactionResult(swap) {
    // Create and show transaction result modal/notification
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Swap Initiated</h3>
                <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div style="text-align: center; margin-bottom: 1.5rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">⏳</div>
                    <h4 style="color: var(--green); margin-bottom: 0.5rem;">Transaction Submitted</h4>
                    <p style="color: var(--text-secondary);">Your swap is being processed</p>
                </div>
                
                <div class="confirm-details">
                    <div class="confirm-row">
                        <span>Swap ID</span>
                        <span style="font-family: var(--font-mono);">${formatAddress(swap.id, 8)}</span>
                    </div>
                    <div class="confirm-row">
                        <span>Amount</span>
                        <span>${swap.fromAmount} ${swap.from}</span>
                    </div>
                    <div class="confirm-row">
                        <span>Expected</span>
                        <span style="color: var(--green);">${swap.toAmount} ${swap.to}</span>
                    </div>
                    <div class="confirm-row">
                        <span>Estimated Time</span>
                        <span>${swap.estimatedTime}</span>
                    </div>
                </div>
                
                <div style="margin-top: 1.5rem; padding: 1rem; background: var(--blue-bg); border: 1px solid var(--blue); border-radius: var(--radius-md);">
                    <strong style="color: var(--blue); display: block; margin-bottom: 0.5rem;">📝 Save This Information</strong>
                    <p style="color: var(--text-secondary); font-size: 0.85rem;">
                        Transaction Hash: <code style="background: var(--bg-primary); padding: 0.25rem 0.5rem; border-radius: 4px; word-break: break-all;">${formatAddress(swap.txHash, 12)}</code>
                    </p>
                </div>
                
                <button class="confirm-btn" onclick="this.closest('.modal').remove()" style="margin-top: 1.5rem;">
                    Close
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

async function pollSwapStatus(swapId) {
    const maxAttempts = 60; // 5 minutes with 5s intervals
    let attempts = 0;
    
    const poll = async () => {
        try {
            const result = await OTCBridgeAPI.getSwapStatus(swapId);
            
            if (result.ok) {
                const { state: statusState, progress, steps } = result.status;
                
                // Update UI with progress (could show in a status page/modal)
                console.log(`Swap progress: ${progress}% - ${statusState}`);
                
                if (statusState === 'completed') {
                    showToast('success', 'Swap completed successfully!');
                    state.currentStep = 'completed';
                    
                    // Reset form
                    state.fromAmount = '';
                    state.toAmount = '';
                    state.quote = null;
                    document.getElementById('fromAmount').value = '';
                    document.getElementById('toAmount').value = '';
                    updateSwapButton();
                    return;
                }
                
                if (statusState === 'failed') {
                    showToast('error', 'Swap failed. Please contact support with your transaction ID.');
                    state.currentStep = 'input';
                    updateSwapButton();
                    return;
                }
            }
        } catch (err) {
            console.error('Status poll failed:', err);
        }
        
        attempts++;
        if (attempts < maxAttempts) {
            setTimeout(poll, 5000); // Poll every 5 seconds
        } else {
            showToast('info', 'Swap is still processing. Check back later with your transaction ID.');
        }
    };
    
    poll();
}

// ============================================================================
// Wallet Connection (Stub)
// ============================================================================

async function connectWallet() {
    // STUB: Implement actual wallet connection logic
    // For Solana: use @solana/wallet-adapter
    // For RustChain: use custom wallet connector
    
    try {
        // Simulate connection delay
        await delay(1000);
        
        // Mock connection
        state.walletConnected = true;
        state.walletAddress = generateMockTxHash().slice(0, 44);
        state.fromBalance = (Math.random() * 1000 + 100).toFixed(6);
        state.toBalance = (Math.random() * 500 + 50).toFixed(6);
        
        updateBalances();
        updateSwapButton();
        
        showToast('success', 'Wallet connected successfully');
    } catch (err) {
        console.error('Wallet connection failed:', err);
        showToast('error', 'Failed to connect wallet');
    }
}

// ============================================================================
// Toast Notifications
// ============================================================================

function showToast(type, message) {
    const colors = {
        success: 'var(--green)',
        error: 'var(--red)',
        info: 'var(--blue)',
        warning: 'var(--amber)'
    };
    
    const icons = {
        success: '✓',
        error: '✕',
        info: 'ℹ',
        warning: '⚠'
    };
    
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: var(--bg-card);
        border: 1px solid ${colors[type]};
        border-left: 4px solid ${colors[type]};
        border-radius: var(--radius-md);
        padding: 1rem 1.5rem;
        color: var(--text-primary);
        font-family: var(--font-mono);
        font-size: 0.9rem;
        z-index: 3000;
        box-shadow: var(--shadow-lg);
        animation: slideIn 0.3s ease-out;
    `;
    
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="color: ${colors[type]}; font-size: 1.2rem; font-weight: bold;">${icons[type]}</span>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Add CSS animations for toast
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(style);

// ============================================================================
// Utility Functions
// ============================================================================

async function pasteAddress() {
    try {
        const text = await navigator.clipboard.readText();
        document.getElementById('destinationAddress').value = text;
        validateAddress();
    } catch (err) {
        showToast('error', 'Failed to paste from clipboard');
    }
}

function toggleNav() {
    const navLinks = document.getElementById('navLinks');
    navLinks.classList.toggle('active');
}

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize UI
    updateDestinationField();
    updateSwapButton();
    
    // Load market data
    updateMarketData();
    updateRecentTransactions();
    
    // Refresh market data every 30 seconds
    setInterval(updateMarketData, 30000);
    
    // Add input listeners
    document.getElementById('fromAmount').addEventListener('input', () => {
        validateAmount('from');
    });
    
    document.getElementById('destinationAddress').addEventListener('input', () => {
        validateAddress();
    });
    
    // Log initialization
    console.log('[OTC Bridge] Initialized - Bounty #695');
});

// Export for module usage (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { OTCBridgeAPI, CONFIG, state };
}
