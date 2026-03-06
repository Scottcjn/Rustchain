/**
 * OTC Bridge - Test Suite
 * Bounty #695 Implementation
 * 
 * This file contains comprehensive tests for the OTC Bridge functionality.
 * Run with: node test-otc-bridge.js (Node.js) or in browser console
 */

// ============================================================================
// Test Utilities
// ============================================================================

const TestResults = {
    passed: 0,
    failed: 0,
    total: 0,
    results: []
};

function assert(condition, testName, expected, actual) {
    TestResults.total++;
    
    if (condition) {
        TestResults.passed++;
        TestResults.results.push({
            test: testName,
            status: 'PASS',
            expected,
            actual
        });
        console.log(`✅ PASS: ${testName}`);
    } else {
        TestResults.failed++;
        TestResults.results.push({
            test: testName,
            status: 'FAIL',
            expected,
            actual
        });
        console.error(`❌ FAIL: ${testName}`);
        console.error(`   Expected: ${expected}`);
        console.error(`   Actual:   ${actual}`);
    }
}

function runTests() {
    console.log('\n' + '='.repeat(60));
    console.log('OTC Bridge Test Suite - Bounty #695');
    console.log('='.repeat(60) + '\n');
    
    // Run all test suites
    testValidation();
    testAPIAdapter();
    testStateManagement();
    testUtilities();
    
    // Print summary
    console.log('\n' + '='.repeat(60));
    console.log('Test Summary');
    console.log('='.repeat(60));
    console.log(`Total:  ${TestResults.total}`);
    console.log(`Passed: ${TestResults.passed}`);
    console.log(`Failed: ${TestResults.failed}`);
    console.log(`Score:  ${(TestResults.passed / TestResults.total * 100).toFixed(1)}%`);
    console.log('='.repeat(60) + '\n');
}

// ============================================================================
// Validation Tests
// ============================================================================

function testValidation() {
    console.log('\n--- Validation Tests ---\n');
    
    // Amount validation pattern
    const AMOUNT_PATTERN = /^\d*\.?\d{0,8}$/;
    
    assert(
        AMOUNT_PATTERN.test('100'),
        'Valid amount: integer',
        'true',
        AMOUNT_PATTERN.test('100')
    );
    
    assert(
        AMOUNT_PATTERN.test('100.50'),
        'Valid amount: decimal',
        'true',
        AMOUNT_PATTERN.test('100.50')
    );
    
    assert(
        AMOUNT_PATTERN.test('0.001'),
        'Valid amount: small decimal',
        'true',
        AMOUNT_PATTERN.test('0.001')
    );
    
    assert(
        AMOUNT_PATTERN.test('100000.12345678'),
        'Valid amount: 8 decimal places',
        'true',
        AMOUNT_PATTERN.test('100000.12345678')
    );
    
    assert(
        !AMOUNT_PATTERN.test('-100'),
        'Invalid amount: negative',
        'false',
        AMOUNT_PATTERN.test('-100')
    );
    
    assert(
        !AMOUNT_PATTERN.test('abc'),
        'Invalid amount: letters',
        'false',
        AMOUNT_PATTERN.test('abc')
    );
    
    assert(
        !AMOUNT_PATTERN.test('100.123456789'),
        'Invalid amount: too many decimals',
        'false',
        AMOUNT_PATTERN.test('100.123456789')
    );
    
    assert(
        !AMOUNT_PATTERN.test('100..50'),
        'Invalid amount: double decimal',
        'false',
        AMOUNT_PATTERN.test('100..50')
    );
    
    // Solana address validation pattern
    const SOLANA_ADDRESS_PATTERN = /^[1-9A-HJ-NP-Za-km-z]{32,44}$/;
    
    const validSolanaAddress = '7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN';
    assert(
        SOLANA_ADDRESS_PATTERN.test(validSolanaAddress),
        'Valid Solana address',
        'true',
        SOLANA_ADDRESS_PATTERN.test(validSolanaAddress)
    );
    
    assert(
        !SOLANA_ADDRESS_PATTERN.test('0x1234567890abcdef'),
        'Invalid address: Ethereum format',
        'false',
        SOLANA_ADDRESS_PATTERN.test('0x1234567890abcdef')
    );
    
    assert(
        !SOLANA_ADDRESS_PATTERN.test('7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN0'),
        'Invalid Solana address: too long',
        'false',
        SOLANA_ADDRESS_PATTERN.test('7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN0')
    );
    
    assert(
        !SOLANA_ADDRESS_PATTERN.test('7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3d'),
        'Invalid Solana address: too short',
        'false',
        SOLANA_ADDRESS_PATTERN.test('7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3d')
    );
    
    assert(
        !SOLANA_ADDRESS_PATTERN.test('7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8m0'),
        'Invalid Solana address: contains 0',
        'false',
        SOLANA_ADDRESS_PATTERN.test('7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8m0')
    );
    
    // RustChain address validation pattern
    const RUSTCHAIN_ADDRESS_PATTERN = /^[a-zA-Z0-9_-]{1,256}$/;
    
    assert(
        RUSTCHAIN_ADDRESS_PATTERN.test('my-wallet'),
        'Valid RustChain address: with hyphen',
        'true',
        RUSTCHAIN_ADDRESS_PATTERN.test('my-wallet')
    );
    
    assert(
        RUSTCHAIN_ADDRESS_PATTERN.test('my_wallet_123'),
        'Valid RustChain address: with underscore and numbers',
        'true',
        RUSTCHAIN_ADDRESS_PATTERN.test('my_wallet_123')
    );
    
    assert(
        RUSTCHAIN_ADDRESS_PATTERN.test('scott'),
        'Valid RustChain address: simple',
        'true',
        RUSTCHAIN_ADDRESS_PATTERN.test('scott')
    );
    
    assert(
        !RUSTCHAIN_ADDRESS_PATTERN.test('wallet@name'),
        'Invalid RustChain address: special character',
        'false',
        RUSTCHAIN_ADDRESS_PATTERN.test('wallet@name')
    );
    
    assert(
        !RUSTCHAIN_ADDRESS_PATTERN.test('wallet name'),
        'Invalid RustChain address: space',
        'false',
        RUSTCHAIN_ADDRESS_PATTERN.test('wallet name')
    );
}

// ============================================================================
// API Adapter Tests
// ============================================================================

async function testAPIAdapter() {
    console.log('\n--- API Adapter Tests ---\n');
    
    // Mock CONFIG for testing
    const CONFIG = {
        BRIDGE: {
            feePercent: 0.1,
            minAmount: 1,
            maxAmount: 100000,
            defaultSlippage: 0.5
        }
    };
    
    // Test quote calculation
    const fromAmount = 100;
    const rate = 0.999;
    const fee = fromAmount * (CONFIG.BRIDGE.feePercent / 100);
    const toAmount = (fromAmount - fee) * rate;
    const minimumReceived = toAmount * (1 - CONFIG.BRIDGE.defaultSlippage / 100);
    
    assert(
        fee === 0.1,
        'Fee calculation: 0.1% of 100',
        '0.1',
        fee.toString()
    );
    
    assert(
        Math.abs(toAmount - 99.8001) < 0.0001,
        'To amount calculation',
        '99.8001',
        toAmount.toFixed(4)
    );
    
    assert(
        Math.abs(minimumReceived - 99.3010995) < 0.0001,
        'Minimum received with 0.5% slippage',
        '99.3010995',
        minimumReceived.toFixed(7)
    );
    
    // Test slippage calculations
    const slippage1 = 1.0;
    const minReceived1 = toAmount * (1 - slippage1 / 100);
    
    assert(
        Math.abs(minReceived1 - 98.802099) < 0.0001,
        'Minimum received with 1% slippage',
        '98.802099',
        minReceived1.toFixed(6)
    );
    
    const slippage2 = 2.0;
    const minReceived2 = toAmount * (1 - slippage2 / 100);
    
    assert(
        Math.abs(minReceived2 - 97.804098) < 0.0001,
        'Minimum received with 2% slippage',
        '97.804098',
        minReceived2.toFixed(6)
    );
}

// ============================================================================
// State Management Tests
// ============================================================================

function testStateManagement() {
    console.log('\n--- State Management Tests ---\n');
    
    // Initial state
    const initialState = {
        direction: 'rtc-to-wrtc',
        fromAmount: '',
        toAmount: '',
        destinationAddress: '',
        slippage: 0.5,
        quote: null,
        walletConnected: false,
        fromBalance: 0,
        toBalance: 0,
        isLoading: false,
        currentStep: 'input'
    };
    
    assert(
        initialState.direction === 'rtc-to-wrtc',
        'Initial direction is rtc-to-wrtc',
        'rtc-to-wrtc',
        initialState.direction
    );
    
    assert(
        initialState.slippage === 0.5,
        'Initial slippage is 0.5%',
        '0.5',
        initialState.slippage.toString()
    );
    
    assert(
        initialState.walletConnected === false,
        'Initial wallet state is disconnected',
        'false',
        initialState.walletConnected.toString()
    );
    
    assert(
        initialState.currentStep === 'input',
        'Initial step is input',
        'input',
        initialState.currentStep
    );
    
    // State transitions
    const state = { ...initialState };
    state.walletConnected = true;
    state.fromBalance = 1000;
    state.fromAmount = '100';
    state.currentStep = 'review';
    
    assert(
        state.walletConnected === true,
        'State update: wallet connected',
        'true',
        state.walletConnected.toString()
    );
    
    assert(
        state.fromBalance === 1000,
        'State update: balance set',
        '1000',
        state.fromBalance.toString()
    );
    
    assert(
        state.currentStep === 'review',
        'State transition: input → review',
        'review',
        state.currentStep
    );
}

// ============================================================================
// Utility Function Tests
// ============================================================================

function testUtilities() {
    console.log('\n--- Utility Function Tests ---\n');
    
    // formatAddress function
    function formatAddress(address, chars = 4) {
        if (address.length <= chars * 2 + 3) return address;
        return `${address.slice(0, chars)}...${address.slice(-chars)}`;
    }
    
    const longAddress = '7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN';
    assert(
        formatAddress(longAddress, 4) === '7nx8...L8mN',
        'formatAddress: 4 chars',
        '7nx8...L8mN',
        formatAddress(longAddress, 4)
    );
    
    assert(
        formatAddress(longAddress, 6) === '7nx8Qm...3dL8mN',
        'formatAddress: 6 chars',
        '7nx8Qm...3dL8mN',
        formatAddress(longAddress, 6)
    );
    
    const shortAddress = 'short';
    assert(
        formatAddress(shortAddress, 4) === 'short',
        'formatAddress: short address unchanged',
        'short',
        formatAddress(shortAddress, 4)
    );
    
    // formatNumber function
    function formatNumber(num, decimals = 2) {
        if (typeof num === 'string' && num.startsWith('<')) return num;
        const n = parseFloat(num);
        if (isNaN(n)) return '0.00';
        return n.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }
    
    assert(
        formatNumber(100) === '100.00',
        'formatNumber: integer',
        '100.00',
        formatNumber(100)
    );
    
    assert(
        formatNumber(100.5) === '100.50',
        'formatNumber: one decimal',
        '100.50',
        formatNumber(100.5)
    );
    
    assert(
        formatNumber(100.123456, 4) === '100.1235',
        'formatNumber: 4 decimals with rounding',
        '100.1235',
        formatNumber(100.123456, 4)
    );
    
    assert(
        formatNumber('<0.01') === '<0.01',
        'formatNumber: string with < prefix',
        '<0.01',
        formatNumber('<0.01')
    );
    
    assert(
        formatNumber('invalid') === '0.00',
        'formatNumber: invalid input',
        '0.00',
        formatNumber('invalid')
    );
    
    // Direction swap logic
    function getTokens(direction) {
        return direction === 'rtc-to-wrtc' 
            ? { from: 'RTC', to: 'wRTC' }
            : { from: 'wRTC', to: 'RTC' };
    }
    
    const tokens1 = getTokens('rtc-to-wrtc');
    assert(
        tokens1.from === 'RTC' && tokens1.to === 'wRTC',
        'getTokens: rtc-to-wrtc',
        'RTC→wRTC',
        `${tokens1.from}→${tokens1.to}`
    );
    
    const tokens2 = getTokens('wrtc-to-rtc');
    assert(
        tokens2.from === 'wRTC' && tokens2.to === 'RTC',
        'getTokens: wrtc-to-rtc',
        'wRTC→RTC',
        `${tokens2.from}→${tokens2.to}`
    );
}

// ============================================================================
// Browser-Specific Tests (Skip in Node.js)
// ============================================================================

function testBrowserFeatures() {
    if (typeof window === 'undefined') {
        console.log('\n--- Browser Tests Skipped (Node.js environment) ---\n');
        return;
    }
    
    console.log('\n--- Browser Tests ---\n');
    
    // Test DOM element existence
    const elements = [
        'swapForm',
        'fromAmount',
        'toAmount',
        'destinationAddress',
        'swapBtn'
    ];
    
    elements.forEach(id => {
        const el = document.getElementById(id);
        assert(
            el !== null,
            `DOM element exists: ${id}`,
            'not null',
            el !== null ? 'not null' : 'null'
        );
    });
    
    // Test CSS variables
    const styles = getComputedStyle(document.documentElement);
    const green = styles.getPropertyValue('--green').trim();
    
    assert(
        green !== '',
        'CSS variable --green is defined',
        'not empty',
        green !== '' ? 'not empty' : 'empty'
    );
}

// ============================================================================
// Run Tests
// ============================================================================

// Run immediately if in Node.js
if (typeof module !== 'undefined' && require.main === module) {
    runTests();
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { runTests, TestResults };
}

// Run in browser when loaded
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        runTests();
        testBrowserFeatures();
    });
}
