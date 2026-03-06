#!/usr/bin/env node

/**
 * OTC Bridge - Example Integration Script
 * Bounty #695 Implementation
 * 
 * This script demonstrates how to integrate with the OTC Bridge API.
 * Run with: node example-integration.js
 * 
 * Prerequisites:
 * - Node.js 14+
 * - npm install node-fetch
 */

// Uncomment for actual API calls
// const fetch = require('node-fetch');

// ============================================================================
// Configuration
// ============================================================================

const CONFIG = {
    API_BASE_URL: 'https://rustchain.org', // Change to your backend
    TOKENS: {
        RTC: { symbol: 'RTC', decimals: 8, network: 'RustChain' },
        wRTC: { symbol: 'wRTC', decimals: 6, network: 'Solana', mint: '12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X' }
    },
    BRIDGE: {
        feePercent: 0.1,
        minAmount: 1,
        maxAmount: 100000,
        defaultSlippage: 0.5
    }
};

// ============================================================================
// API Client Class
// ============================================================================

class OTCBridgeClient {
    constructor(baseUrl = CONFIG.API_BASE_URL) {
        this.baseUrl = baseUrl;
    }
    
    /**
     * Get a quote for swapping tokens
     */
    async getQuote(params) {
        const { from, to, amount, slippage = CONFIG.BRIDGE.defaultSlippage } = params;
        
        // Validate parameters
        this.validateToken(from);
        this.validateToken(to);
        this.validateAmount(amount);
        
        console.log(`\n📊 Getting Quote:`);
        console.log(`   From: ${amount} ${from}`);
        console.log(`   To: ${to}`);
        console.log(`   Slippage: ${slippage}%`);
        
        // MOCK IMPLEMENTATION - Replace with actual API call
        // const url = `${this.baseUrl}/api/otc/quote?from=${from}&to=${to}&amount=${amount}&slippage=${slippage}`;
        // const response = await fetch(url);
        // return response.json();
        
        // Simulated response
        await this.delay(500);
        
        const rate = from === 'RTC' && to === 'wRTC' ? 0.999 : 1.001;
        const fee = amount * (CONFIG.BRIDGE.feePercent / 100);
        const toAmount = (amount - fee) * rate;
        
        const quote = {
            ok: true,
            quote: {
                id: `quote_${Date.now()}`,
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
                validUntil: Math.floor(Date.now() / 1000) + 300,
                createdAt: Math.floor(Date.now() / 1000)
            }
        };
        
        this.printQuote(quote.quote);
        return quote;
    }
    
    /**
     * Execute a swap
     */
    async executeSwap(params) {
        const { from, to, fromAmount, toAddress, slippage, quoteId } = params;
        
        console.log(`\n🔄 Executing Swap:`);
        console.log(`   From: ${fromAmount} ${from}`);
        console.log(`   To: ${to}`);
        console.log(`   Destination: ${toAddress}`);
        console.log(`   Quote ID: ${quoteId}`);
        
        // MOCK IMPLEMENTATION - Replace with actual API call
        // const response = await fetch(`${this.baseUrl}/api/otc/swap`, {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(params)
        // });
        // return response.json();
        
        await this.delay(1000);
        
        const swap = {
            ok: true,
            swap: {
                id: `swap_${Date.now()}`,
                status: 'pending',
                from,
                to,
                fromAmount: fromAmount.toString(),
                toAmount: '99.900000',
                txHash: this.generateMockTxHash(),
                estimatedTime: '5-30 minutes',
                createdAt: Math.floor(Date.now() / 1000)
            }
        };
        
        this.printSwap(swap.swap);
        return swap;
    }
    
    /**
     * Check swap status
     */
    async getSwapStatus(swapId) {
        console.log(`\n📍 Checking Status: ${swapId}`);
        
        // MOCK IMPLEMENTATION - Replace with actual API call
        // const response = await fetch(`${this.baseUrl}/api/otc/status/${swapId}`);
        // return response.json();
        
        await this.delay(300);
        
        const status = {
            ok: true,
            status: {
                id: swapId,
                state: 'processing',
                progress: Math.floor(Math.random() * 60) + 20,
                steps: [
                    { name: 'initiated', completed: true, timestamp: Date.now() - 120000 },
                    { name: 'locked', completed: true, timestamp: Date.now() - 60000 },
                    { name: 'bridging', completed: false, timestamp: null },
                    { name: 'completed', completed: false, timestamp: null }
                ]
            }
        };
        
        this.printStatus(status.status);
        return status;
    }
    
    /**
     * Get market data
     */
    async getMarketData() {
        console.log(`\n📈 Getting Market Data:`);
        
        // MOCK IMPLEMENTATION
        await this.delay(300);
        
        return {
            ok: true,
            data: {
                volume24h: (Math.random() * 100000 + 50000).toFixed(2),
                liquidity: (Math.random() * 1000000 + 500000).toFixed(2),
                lastPrice: '1.00',
                priceChange24h: (Math.random() * 4 - 2).toFixed(2)
            }
        };
    }
    
    // ========================================================================
    // Validation Helpers
    // ========================================================================
    
    validateToken(symbol) {
        if (!CONFIG.TOKENS[symbol]) {
            throw new Error(`Invalid token: ${symbol}. Must be RTC or wRTC`);
        }
    }
    
    validateAmount(amount) {
        if (amount < CONFIG.BRIDGE.minAmount) {
            throw new Error(`Amount ${amount} is below minimum ${CONFIG.BRIDGE.minAmount}`);
        }
        if (amount > CONFIG.BRIDGE.maxAmount) {
            throw new Error(`Amount ${amount} is above maximum ${CONFIG.BRIDGE.maxAmount}`);
        }
    }
    
    // ========================================================================
    // Utility Helpers
    // ========================================================================
    
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    generateMockTxHash() {
        const chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
        let hash = '';
        for (let i = 0; i < 88; i++) {
            hash += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return hash;
    }
    
    formatAddress(address, chars = 4) {
        if (address.length <= chars * 2 + 3) return address;
        return `${address.slice(0, chars)}...${address.slice(-chars)}`;
    }
    
    // ========================================================================
    // Print Helpers
    // ========================================================================
    
    printQuote(quote) {
        console.log(`\n✅ Quote Received:`);
        console.log(`   Quote ID: ${quote.id}`);
        console.log(`   Rate: 1 ${quote.from} = ${parseFloat(quote.rate).toFixed(4)} ${quote.to}`);
        console.log(`   You'll get: ${quote.toAmount} ${quote.to}`);
        console.log(`   Fee: ${quote.fee} ${quote.from} (${quote.feePercent})`);
        console.log(`   Minimum received: ${quote.minimumReceived} ${quote.to}`);
        console.log(`   Price impact: ${quote.priceImpact}`);
        console.log(`   Valid until: ${new Date(quote.validUntil * 1000).toLocaleTimeString()}`);
    }
    
    printSwap(swap) {
        console.log(`\n✅ Swap Initiated:`);
        console.log(`   Swap ID: ${swap.id}`);
        console.log(`   Status: ${swap.status}`);
        console.log(`   Transaction: ${this.formatAddress(swap.txHash, 8)}`);
        console.log(`   Estimated time: ${swap.estimatedTime}`);
    }
    
    printStatus(status) {
        console.log(`\n📊 Status Update:`);
        console.log(`   State: ${status.state}`);
        console.log(`   Progress: ${status.progress}%`);
        console.log(`   Steps:`);
        status.steps.forEach(step => {
            const icon = step.completed ? '✅' : '⏳';
            console.log(`     ${icon} ${step.name}`);
        });
    }
}

// ============================================================================
// Example Usage
// ============================================================================

async function runExample() {
    console.log('='.repeat(60));
    console.log('OTC Bridge Integration Example - Bounty #695');
    console.log('='.repeat(60));
    
    const client = new OTCBridgeClient();
    
    try {
        // Example 1: Get a quote
        console.log('\n' + '='.repeat(60));
        console.log('Example 1: Get Quote');
        console.log('='.repeat(60));
        
        const quoteResult = await client.getQuote({
            from: 'RTC',
            to: 'wRTC',
            amount: 100,
            slippage: 0.5
        });
        
        if (!quoteResult.ok) {
            throw new Error(quoteResult.error?.message || 'Quote failed');
        }
        
        const quote = quoteResult.quote;
        
        // Example 2: Execute swap
        console.log('\n' + '='.repeat(60));
        console.log('Example 2: Execute Swap');
        console.log('='.repeat(60));
        
        const swapResult = await client.executeSwap({
            from: quote.from,
            to: quote.to,
            fromAmount: quote.fromAmount,
            toAddress: '7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN',
            slippage: parseFloat(quote.slippage),
            quoteId: quote.id
        });
        
        if (!swapResult.ok) {
            throw new Error(swapResult.error?.message || 'Swap failed');
        }
        
        const swap = swapResult.swap;
        
        // Example 3: Poll status
        console.log('\n' + '='.repeat(60));
        console.log('Example 3: Poll Status');
        console.log('='.repeat(60));
        
        // Poll 3 times to show progression
        for (let i = 0; i < 3; i++) {
            await client.delay(1000);
            const statusResult = await client.getSwapStatus(swap.id);
            
            if (statusResult.ok && statusResult.status.state === 'completed') {
                console.log('\n🎉 Swap completed successfully!');
                break;
            }
        }
        
        // Example 4: Get market data
        console.log('\n' + '='.repeat(60));
        console.log('Example 4: Market Data');
        console.log('='.repeat(60));
        
        const marketResult = await client.getMarketData();
        if (marketResult.ok) {
            const data = marketResult.data;
            console.log(`   24h Volume: $${parseFloat(data.volume24h).toLocaleString()}`);
            console.log(`   Liquidity: $${parseFloat(data.liquidity).toLocaleString()}`);
            console.log(`   Last Price: ${data.lastPrice}`);
            console.log(`   24h Change: ${data.priceChange24h}%`);
        }
        
        // Summary
        console.log('\n' + '='.repeat(60));
        console.log('Example Complete!');
        console.log('='.repeat(60));
        console.log('\nTo use with real API:');
        console.log('1. Install node-fetch: npm install node-fetch');
        console.log('2. Uncomment fetch imports');
        console.log('3. Replace mock implementations with actual API calls');
        console.log('4. Update CONFIG.API_BASE_URL to your backend');
        
    } catch (error) {
        console.error('\n❌ Error:', error.message);
        process.exit(1);
    }
}

// Run example
runExample().catch(console.error);
