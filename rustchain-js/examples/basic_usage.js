/**
 * Basic RustChain SDK Usage Examples
 * 
 * This file demonstrates basic usage of the RustChain JavaScript SDK.
 */

import { RustChainClient, Wallet, Transaction } from '../src/index.js';
import { 
  RustChainError, 
  NetworkError, 
  AuthenticationError 
} from '../src/errors.js';

/**
 * Example 1: Query wallet balance
 */
async function exampleBasicBalanceQuery() {
  console.log('='.repeat(60));
  console.log('Example 1: Query Wallet Balance');
  console.log('='.repeat(60));
  
  const client = new RustChainClient({
    nodeUrl: 'https://50.28.86.131',
  });
  
  try {
    // Query balance
    const balance = await client.getBalance('RTC4325af95d26d59c3ef025963656d22af638bb96b');
    
    if (balance.error) {
      console.log(`Error: ${balance.error}`);
    } else {
      console.log(`Miner ID: ${balance.miner_id}`);
      console.log(`Balance: ${balance.balance_rtc} RTC`);
      console.log(`USD Value: $${(balance.balance_rtc * 0.10).toFixed(2)}`);
    }
  } catch (error) {
    if (error instanceof NetworkError) {
      console.log(`Network error: ${error.message}`);
    } else if (error instanceof RustChainError) {
      console.log(`API error: ${error.message}`);
    }
  }
}

/**
 * Example 2: Wallet operations
 */
async function exampleWalletOperations() {
  console.log('\n' + '='.repeat(60));
  console.log('Example 2: Wallet Operations');
  console.log('='.repeat(60));
  
  const client = new RustChainClient();
  const wallet = new Wallet(client);
  
  const walletName = 'my-test-wallet';
  
  // Validate wallet name
  const [isValid, msg] = wallet.validateName(walletName);
  console.log(`Validating '${walletName}': ${msg}`);
  
  // Check if wallet exists
  const exists = await wallet.exists(walletName);
  console.log(`Wallet exists: ${exists}`);
  
  // Get balance
  const balance = await wallet.getBalance(walletName);
  console.log(`Balance: ${balance} RTC`);
  
  // Get pending transfers
  const pending = await wallet.getPending(walletName);
  console.log(`Pending transfers: ${pending.length}`);
  
  // Show registration guide (first 500 chars)
  console.log('\nRegistration Guide:');
  const guide = wallet.registrationGuide('new-wallet-name');
  console.log(guide.substring(0, 500) + '...');
}

/**
 * Example 3: Network information
 */
async function exampleNetworkInfo() {
  console.log('\n' + '='.repeat(60));
  console.log('Example 3: Network Information');
  console.log('='.repeat(60));
  
  const client = new RustChainClient();
  
  try {
    // Get epoch info
    const epoch = await client.getEpochInfo();
    console.log(`Current Epoch: ${epoch.epoch || 'N/A'}`);
    console.log(`Current Slot: ${epoch.slot || 'N/A'}`);
    console.log(`Enrolled Miners: ${(epoch.enrolled_miners || []).length}`);
    
    // Get active miners
    const miners = await client.getActiveMiners();
    console.log(`\nActive Miners: ${miners.length}`);
    if (miners.length > 0) {
      console.log('Top 5 miners:');
      miners.slice(0, 5).forEach(miner => {
        console.log(`  - ${miner.miner_id || 'Unknown'}`);
      });
    }
    
    // Health check
    const health = await client.healthCheck();
    console.log(`\nNode Health: ${health.status || 'Unknown'}`);
  } catch (error) {
    console.log(`Error: ${error.message}`);
  }
}

/**
 * Example 4: Admin operations (requires admin key)
 */
async function exampleAdminOperations() {
  console.log('\n' + '='.repeat(60));
  console.log('Example 4: Admin Operations');
  console.log('='.repeat(60));
  
  // Note: Replace with actual admin key for real usage
  const client = new RustChainClient({
    adminKey: 'your-admin-key-here',
  });
  
  try {
    // Get all holders
    console.log('Fetching all wallet holders...');
    const holders = await client.getAllHolders();
    
    if (Array.isArray(holders) && holders.length > 0) {
      console.log(`Total holders: ${holders.length}`);
      console.log('\nTop 10 holders:');
      holders.slice(0, 10).forEach(holder => {
        const minerId = holder.miner_id || 'Unknown';
        const amount = holder.amount_rtc || 0;
        const category = holder.category || 'unknown';
        console.log(`  ${minerId.substring(0, 20).padEnd(20)} ${amount.toFixed(2).padStart(10)} RTC [${category}]`);
      });
    }
    
    // Get holder statistics
    const stats = await client.getHolderStats();
    console.log('\nHolder Statistics:');
    console.log(`  Total wallets: ${stats.total_wallets || 0}`);
    console.log(`  With balance: ${stats.wallets_with_balance || 0}`);
    console.log(`  Total RTC: ${(stats.total_rtc || 0).toFixed(2)}`);
  } catch (error) {
    if (error instanceof AuthenticationError) {
      console.log('Admin key required! Set adminKey parameter.');
    } else {
      console.log(`Error: ${error.message}`);
    }
  }
}

/**
 * Example 5: Transaction operations
 */
async function exampleTransaction() {
  console.log('\n' + '='.repeat(60));
  console.log('Example 5: Transaction Operations');
  console.log('='.repeat(60));
  
  // Note: Replace with actual admin key for real usage
  const client = new RustChainClient({
    adminKey: 'your-admin-key-here',
  });
  const tx = new Transaction(client);
  
  const fromWallet = 'wallet1';
  const toWallet = 'wallet2';
  const amount = 10.0;
  
  // Build transaction preview
  const preview = tx.buildTransfer(fromWallet, toWallet, amount);
  console.log('Transaction Preview:');
  console.log(`  From: ${preview.from_miner}`);
  console.log(`  To: ${preview.to_miner}`);
  console.log(`  Amount: ${preview.amount_rtc} RTC`);
  console.log(`  Status: ${preview.status}`);
  
  // Validate transaction
  const [isValid, msg] = await tx.validateTransfer(fromWallet, toWallet, amount);
  console.log(`\nValidation: ${msg}`);
  
  // Send transaction (commented out - requires real admin key)
  // if (isValid) {
  //   const result = await tx.send(fromWallet, toWallet, amount);
  //   console.log(`Transaction sent! ID: ${result.pending_id}`);
  // }
}

/**
 * Example 6: Error handling patterns
 */
async function exampleErrorHandling() {
  console.log('\n' + '='.repeat(60));
  console.log('Example 6: Error Handling Patterns');
  console.log('='.repeat(60));
  
  // Test with invalid node URL
  const clientInvalid = new RustChainClient({
    nodeUrl: 'https://invalid-url.example.com',
  });
  
  try {
    await clientInvalid.getBalance('test-wallet');
  } catch (error) {
    if (error instanceof NetworkError) {
      console.log(`✓ Caught NetworkError: ${error.message}`);
    } else if (error instanceof RustChainError) {
      console.log(`✓ Caught RustChainError: ${error.message}`);
    }
  }
  
  // Test with missing admin key
  const clientNoAuth = new RustChainClient();
  
  try {
    await clientNoAuth.transferRtc('wallet1', 'wallet2', 10.0);
  } catch (error) {
    if (error instanceof AuthenticationError) {
      console.log(`✓ Caught AuthenticationError: ${error.message}`);
    }
  }
  
  // Test with invalid wallet
  const clientValid = new RustChainClient();
  
  try {
    const result = await clientValid.getBalance('');
    if (result.error) {
      console.log(`✓ Handled API error: ${result.error}`);
    }
  } catch (error) {
    console.log(`✓ Caught RustChainError: ${error.message}`);
  }
}

/**
 * Run all examples
 */
async function main() {
  console.log('\n🦀 RustChain JavaScript SDK Examples\n');
  
  await exampleBasicBalanceQuery();
  await exampleWalletOperations();
  await exampleNetworkInfo();
  await exampleAdminOperations();
  await exampleTransaction();
  await exampleErrorHandling();
  
  console.log('\n' + '='.repeat(60));
  console.log('All examples completed!');
  console.log('='.repeat(60));
}

// Run examples
main().catch(console.error);
