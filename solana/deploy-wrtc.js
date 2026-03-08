/**
 * RIP-305 Track A: wRTC SPL Token Deployment Script
 * Deploys wrapped RTC (wRTC) as an SPL Token on Solana devnet
 * 
 * Bounty: #1149 (RIP-305 Cross-Chain Airdrop) - Track A (75 RTC)
 * Agent: nox-ventures | GitHub: noxxxxybot-sketch
 */

const {
  Connection,
  Keypair,
  PublicKey,
  SystemProgram,
  Transaction,
  sendAndConfirmTransaction,
  LAMPORTS_PER_SOL,
} = require('@solana/web3.js');

const {
  createMint,
  getOrCreateAssociatedTokenAccount,
  mintTo,
  TOKEN_PROGRAM_ID,
  MINT_SIZE,
  createInitializeMintInstruction,
  getMinimumBalanceForRentExemptMint,
  createSetAuthorityInstruction,
  AuthorityType,
} = require('@solana/spl-token');

const fs = require('fs');

// ============================================================
// CONFIGURATION
// ============================================================
const NETWORK = process.env.SOLANA_NETWORK || 'devnet';
const RPC_URL = NETWORK === 'mainnet-beta'
  ? 'https://api.mainnet-beta.solana.com'
  : 'https://api.devnet.solana.com';

// wRTC Token Specification (RIP-305)
const TOKEN_CONFIG = {
  name: 'Wrapped RTC',
  symbol: 'wRTC',
  decimals: 6,              // Matches RTC internal precision
  description: 'Wrapped RustChain Token (wRTC) on Solana — cross-chain bridge asset for RIP-305 airdrop',
  totalAllocation: 30_000,  // 30,000 wRTC for Solana pool (RIP-305 spec)
  uri: 'https://rustchain.org/wrtc-metadata.json',
};

// Keypair file path (generated if not exists)
const KEYPAIR_PATH = process.env.KEYPAIR_PATH || '/tmp/wrtc-deploy-keypair.json';
const MINT_KEYPAIR_PATH = process.env.MINT_KEYPAIR_PATH || '/tmp/wrtc-mint-keypair.json';

// ============================================================
// HELPERS
// ============================================================
function loadOrCreateKeypair(path) {
  if (fs.existsSync(path)) {
    const data = JSON.parse(fs.readFileSync(path, 'utf-8'));
    return Keypair.fromSecretKey(Buffer.from(data));
  }
  const kp = Keypair.generate();
  fs.writeFileSync(path, JSON.stringify(Array.from(kp.secretKey)));
  console.log(`Generated new keypair: ${path}`);
  return kp;
}

async function requestAirdropIfNeeded(connection, pubkey, minBalance = 1.0) {
  const balance = await connection.getBalance(pubkey);
  const balanceSOL = balance / LAMPORTS_PER_SOL;
  console.log(`  Balance: ${balanceSOL.toFixed(4)} SOL`);
  
  if (balanceSOL < minBalance && NETWORK === 'devnet') {
    console.log(`  Requesting devnet airdrop...`);
    const sig = await connection.requestAirdrop(pubkey, 2 * LAMPORTS_PER_SOL);
    await connection.confirmTransaction(sig, 'confirmed');
    const newBalance = await connection.getBalance(pubkey);
    console.log(`  New balance: ${(newBalance / LAMPORTS_PER_SOL).toFixed(4)} SOL`);
  }
}

// ============================================================
// MAIN DEPLOYMENT
// ============================================================
async function deployWRTC() {
  console.log('═══════════════════════════════════════════');
  console.log('  RIP-305 Track A: wRTC SPL Token Deployment');
  console.log(`  Network: ${NETWORK}`);
  console.log('═══════════════════════════════════════════\n');

  // Connect
  const connection = new Connection(RPC_URL, 'confirmed');
  const slot = await connection.getSlot();
  console.log(`✅ Connected to ${NETWORK} (slot: ${slot})\n`);

  // Load/create deploy authority keypair
  const deployAuthority = loadOrCreateKeypair(KEYPAIR_PATH);
  console.log(`Deploy authority: ${deployAuthority.publicKey.toBase58()}`);
  await requestAirdropIfNeeded(connection, deployAuthority.publicKey);
  console.log('');

  // Load/create mint keypair (deterministic address for the mint)
  const mintKeypair = loadOrCreateKeypair(MINT_KEYPAIR_PATH);
  console.log(`Mint address: ${mintKeypair.publicKey.toBase58()}`);
  console.log('');

  // Check if mint already exists
  let mintInfo;
  try {
    mintInfo = await connection.getAccountInfo(mintKeypair.publicKey);
    if (mintInfo) {
      console.log('ℹ️  Mint already exists, skipping creation');
    }
  } catch (e) {
    mintInfo = null;
  }

  let mintAddress;

  if (!mintInfo) {
    console.log('📦 Creating wRTC SPL Token mint...');
    
    // Create the mint
    mintAddress = await createMint(
      connection,
      deployAuthority,          // payer
      deployAuthority.publicKey, // mint authority
      deployAuthority.publicKey, // freeze authority (will transfer to null or multisig)
      TOKEN_CONFIG.decimals,     // 6 decimals (matches RTC)
      mintKeypair,              // mint keypair (determines address)
    );
    
    console.log(`✅ Mint created: ${mintAddress.toBase58()}`);
    console.log(`   Decimals: ${TOKEN_CONFIG.decimals}`);
    console.log(`   Mint authority: ${deployAuthority.publicKey.toBase58()}`);
    console.log('');
  } else {
    mintAddress = mintKeypair.publicKey;
    console.log(`ℹ️  Using existing mint: ${mintAddress.toBase58()}\n`);
  }

  // Create associated token account for deploy authority
  console.log('📂 Creating token account for deploy authority...');
  const tokenAccount = await getOrCreateAssociatedTokenAccount(
    connection,
    deployAuthority,
    mintAddress,
    deployAuthority.publicKey,
  );
  console.log(`✅ Token account: ${tokenAccount.address.toBase58()}`);
  console.log('');

  // Mint the full allocation (30,000 wRTC)
  const mintAmount = BigInt(TOKEN_CONFIG.totalAllocation) * BigInt(10 ** TOKEN_CONFIG.decimals);
  console.log(`💰 Minting ${TOKEN_CONFIG.totalAllocation} wRTC (${mintAmount} raw units)...`);
  
  const mintSig = await mintTo(
    connection,
    deployAuthority,
    mintAddress,
    tokenAccount.address,
    deployAuthority.publicKey,
    mintAmount,
  );
  console.log(`✅ Minted: https://explorer.solana.com/tx/${mintSig}?cluster=${NETWORK}`);
  console.log('');

  // Verify balance
  const finalBalance = await connection.getTokenAccountBalance(tokenAccount.address);
  console.log(`📊 Token balance: ${finalBalance.value.uiAmountString} wRTC`);
  console.log('');

  // Output deployment summary
  const summary = {
    network: NETWORK,
    token: TOKEN_CONFIG,
    mintAddress: mintAddress.toBase58(),
    mintAuthority: deployAuthority.publicKey.toBase58(),
    treasury: tokenAccount.address.toBase58(),
    mintSignature: mintSig,
    totalMinted: TOKEN_CONFIG.totalAllocation,
    explorerUrl: `https://explorer.solana.com/address/${mintAddress.toBase58()}?cluster=${NETWORK}`,
    timestamp: new Date().toISOString(),
    rip305: {
      bounty: '#1149',
      track: 'A — Solana SPL Token',
      reward: '75 RTC',
      wallet: 'nox-ventures',
    },
  };

  fs.writeFileSync('/tmp/wrtc-deployment.json', JSON.stringify(summary, null, 2));
  console.log('═══════════════════════════════════════════');
  console.log('  DEPLOYMENT SUMMARY');
  console.log('═══════════════════════════════════════════');
  console.log(JSON.stringify(summary, null, 2));
  
  console.log('\n📋 Next steps for mainnet:');
  console.log('1. Fund mainnet wallet with SOL (~0.05 SOL needed for fees)');
  console.log('2. Set SOLANA_NETWORK=mainnet-beta and run again');
  console.log('3. Transfer mint authority to Elyan Labs multisig');
  console.log('4. Register token metadata via Metaplex Token Metadata');
  console.log('5. Submit deployment to #1149 as Track A delivery');
  
  return summary;
}

// Run
deployWRTC().then(r => {
  process.exit(0);
}).catch(err => {
  console.error('❌ Deployment failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
