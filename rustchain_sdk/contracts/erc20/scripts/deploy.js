/**
 * Deployment Script for RustChain wRTC ERC-20 on Base
 * 
 * Usage:
 *   npx hardhat run scripts/deploy.js --network base
 *   npx hardhat run scripts/deploy.js --network baseSepolia
 * 
 * Environment variables:
 *   - INITIAL_SUPPLY: Initial supply in tokens (default: 1000000 = 1M wRTC)
 *   - BRIDGE_OPERATOR: Bridge operator address (default: deployer address)
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

// Configuration
const INITIAL_SUPPLY_ETH = process.env.INITIAL_SUPPLY || "1000000"; // 1M tokens
const DECIMALS = 6n; // wRTC uses 6 decimals

async function main() {
  console.log("=".repeat(60));
  console.log("RustChain wRTC ERC-20 Deployment");
  console.log("RIP-305 Track B - Bounty #1510");
  console.log("=".repeat(60));
  
  const [deployer] = await hre.ethers.getSigners();
  const network = await hre.ethers.provider.getNetwork();
  
  console.log("\n📋 Deployment Configuration:");
  console.log(`   Network: ${network.name} (Chain ID: ${network.chainId})`);
  console.log(`   Deployer: ${deployer.address}`);
  console.log(`   Initial Supply: ${INITIAL_SUPPLY_ETH} wRTC`);
  
  // Calculate initial supply in atomic units
  const initialSupply = parseTokenAmount(INITIAL_SUPPLY_ETH);
  console.log(`   Initial Supply (atomic): ${initialSupply.toString()}`);
  
  // Get bridge operator address (default to deployer)
  const bridgeOperator = process.env.BRIDGE_OPERATOR || deployer.address;
  console.log(`   Bridge Operator: ${bridgeOperator}`);
  
  // Check deployer balance
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`   Deployer Balance: ${hre.ethers.formatEther(balance)} ETH`);
  
  if (balance === 0n) {
    console.log("\n❌ ERROR: Deployer has no ETH for gas fees!");
    console.log("   Please fund the deployer address with ETH.");
    process.exit(1);
  }
  
  console.log("\n🚀 Deploying WRTC contract...");
  
  // Deploy the contract
  const WRTC = await hre.ethers.getContractFactory("WRTC");
  const wrtc = await WRTC.deploy(initialSupply, bridgeOperator);
  
  console.log("   Waiting for deployment transaction...");
  await wrtc.waitForDeployment();
  
  const contractAddress = await wrtc.getAddress();
  const deploymentTx = wrtc.deploymentTransaction();
  
  console.log("\n✅ Contract Deployed Successfully!");
  console.log("=".repeat(60));
  console.log(`📍 Contract Address: ${contractAddress}`);
  console.log(`📝 Deployment Tx: ${deploymentTx.hash}`);
  console.log(`🔗 View on BaseScan: https://${network.chainId === 84532 ? 'sepolia.' : ''}basescan.org/address/${contractAddress}`);
  console.log("=".repeat(60));
  
  // Verify contract details
  console.log("\n📊 Contract Verification:");
  const name = await wrtc.name();
  const symbol = await wrtc.symbol();
  const decimals = await wrtc.decimals();
  const totalSupply = await wrtc.totalSupply();
  const deployerBalance = await wrtc.balanceOf(deployer.address);
  const isBridgeOperator = await wrtc.bridgeOperators(bridgeOperator);
  
  console.log(`   Name: ${name}`);
  console.log(`   Symbol: ${symbol}`);
  console.log(`   Decimals: ${decimals}`);
  console.log(`   Total Supply: ${formatTokenAmount(totalSupply)} wRTC`);
  console.log(`   Deployer Balance: ${formatTokenAmount(deployerBalance)} wRTC`);
  console.log(`   Bridge Operator Set: ${isBridgeOperator}`);
  
  // Save deployment info
  const deploymentInfo = {
    contractName: "WRTC",
    contractAddress: contractAddress,
    deploymentTx: deploymentTx.hash,
    deploymentBlock: deploymentTx.blockNumber,
    network: {
      name: network.name,
      chainId: Number(network.chainId),
    },
    deployer: deployer.address,
    configuration: {
      initialSupply: initialSupply.toString(),
      initialSupplyFormatted: formatTokenAmount(initialSupply),
      bridgeOperator: bridgeOperator,
      decimals: Number(decimals),
    },
    deployedAt: new Date().toISOString(),
  };
  
  const artifactsDir = path.join(__dirname, "..", "artifacts", "deployments");
  fs.mkdirSync(artifactsDir, { recursive: true });
  
  const networkName = network.chainId === 8453 ? "base" : 
                      network.chainId === 84532 ? "base-sepolia" : 
                      `chain-${network.chainId}`;
  
  const filePath = path.join(artifactsDir, `${networkName}-WRTC.json`);
  fs.writeFileSync(filePath, JSON.stringify(deploymentInfo, null, 2));
  
  console.log(`\n💾 Deployment info saved to: ${filePath}`);
  
  // Verification instructions
  console.log("\n🔍 Next Steps:");
  console.log("   1. Verify contract on BaseScan:");
  console.log(`      npx hardhat verify --network ${network.name} ${contractAddress} ${initialSupply} ${bridgeOperator}`);
  console.log("\n   2. Add contract to wallet:");
  console.log(`      Address: ${contractAddress}`);
  console.log(`      Symbol: wRTC`);
  console.log(`      Decimals: ${decimals}`);
  console.log("\n   3. Configure bridge operators:");
  console.log(`      await wrtc.addBridgeOperator('0x...')`);
  
  console.log("\n" + "=".repeat(60));
  console.log("Deployment Complete! 🎉");
  console.log("=".repeat(60));
  
  return deploymentInfo;
}

/**
 * Parse token amount to atomic units
 */
function parseTokenAmount(amountStr) {
  const amount = BigInt(Math.floor(parseFloat(amountStr) * Math.pow(10, 6)));
  return amount;
}

/**
 * Format atomic units to token amount
 */
function formatTokenAmount(amount) {
  return (Number(amount) / Math.pow(10, 6)).toLocaleString();
}

// Execute deployment
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:", error);
    process.exit(1);
  });
