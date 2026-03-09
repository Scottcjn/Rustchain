/**
 * Contract Interaction Script
 * 
 * Common operations for WRTC token management
 * 
 * Usage examples:
 *   node scripts/interact.js balance <address>
 *   node scripts/interact.js transfer <to> <amount>
 *   node scripts/interact.js add-operator <operator-address>
 *   node scripts/interact.js pause
 *   node scripts/interact.js info
 */

const hre = require("hardhat");
const { ethers } = require("hardhat");

const WRTC_ABI = [
  "function name() view returns (string)",
  "function symbol() view returns (string)",
  "function decimals() view returns (uint8)",
  "function totalSupply() view returns (uint256)",
  "function balanceOf(address) view returns (uint256)",
  "function transfer(address to, uint256 amount) returns (bool)",
  "function approve(address spender, uint256 amount) returns (bool)",
  "function allowance(address owner, address spender) view returns (uint256)",
  "function burn(uint256 amount)",
  "function burnFrom(address account, uint256 amount)",
  "function bridgeOperators(address) view returns (bool)",
  "function addBridgeOperator(address operator)",
  "function removeBridgeOperator(address operator)",
  "function pause()",
  "function unpause()",
  "function paused() view returns (bool)",
];

async function main() {
  const [deployer] = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();
  
  // Get contract address from environment or deployment file
  const contractAddress = process.env.WRTC_ADDRESS || getDeploymentAddress(network.chainId);
  
  if (!contractAddress) {
    console.log("❌ ERROR: WRTC_ADDRESS not set and no deployment found");
    console.log("\nSet environment variable:");
    console.log("  export WRTC_ADDRESS=0x...");
    process.exit(1);
  }
  
  console.log(`Network: ${network.name} (Chain ID: ${network.chainId})`);
  console.log(`Contract: ${contractAddress}`);
  console.log(`Account: ${deployer.address}`);
  console.log("-".repeat(60));
  
  const wrtc = new ethers.Contract(contractAddress, WRTC_ABI, deployer);
  
  const command = process.argv[2];
  const args = process.argv.slice(3);
  
  switch (command) {
    case "info":
      await showInfo(wrtc);
      break;
    case "balance":
      await getBalance(wrtc, args[0] || deployer.address);
      break;
    case "transfer":
      await transfer(wrtc, args[0], args[1]);
      break;
    case "approve":
      await approve(wrtc, args[0], args[1]);
      break;
    case "allowance":
      await getAllowance(wrtc, args[0], args[1] || deployer.address);
      break;
    case "burn":
      await burn(wrtc, args[0]);
      break;
    case "add-operator":
      await addOperator(wrtc, args[0]);
      break;
    case "remove-operator":
      await removeOperator(wrtc, args[0]);
      break;
    case "pause":
      await pause(wrtc);
      break;
    case "unpause":
      await unpause(wrtc);
      break;
    case "bridge-mint":
      await bridgeMint(wrtc, args[0], args[1]);
      break;
    case "bridge-burn":
      await bridgeBurn(wrtc, args[0], args[1]);
      break;
    default:
      showHelp();
  }
}

async function showInfo(contract) {
  const [name, symbol, decimals, totalSupply, paused] = await Promise.all([
    contract.name(),
    contract.symbol(),
    contract.decimals(),
    contract.totalSupply(),
    contract.paused(),
  ]);
  
  console.log("\n📊 WRTC Token Info:");
  console.log(`   Name: ${name}`);
  console.log(`   Symbol: ${symbol}`);
  console.log(`   Decimals: ${decimals}`);
  console.log(`   Total Supply: ${formatAmount(totalSupply, decimals)} wRTC`);
  console.log(`   Paused: ${paused}`);
}

async function getBalance(contract, address) {
  const balance = await contract.balanceOf(address);
  const decimals = await contract.decimals();
  console.log(`\n💰 Balance of ${address}:`);
  console.log(`   ${formatAmount(balance, decimals)} wRTC`);
}

async function transfer(contract, to, amountStr) {
  if (!to || !amountStr) {
    console.log("❌ Usage: transfer <to_address> <amount>");
    return;
  }
  
  const amount = parseAmount(amountStr, await contract.decimals());
  console.log(`\n📤 Transferring ${amountStr} wRTC to ${to}...`);
  
  const tx = await contract.transfer(to, amount);
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function approve(contract, spender, amountStr) {
  if (!spender || !amountStr) {
    console.log("❌ Usage: approve <spender> <amount>");
    return;
  }
  
  const amount = parseAmount(amountStr, await contract.decimals());
  console.log(`\n✅ Approving ${spender} to spend ${amountStr} wRTC...`);
  
  const tx = await contract.approve(spender, amount);
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function getAllowance(contract, spender, owner) {
  const allowance = await contract.allowance(owner, spender);
  const decimals = await contract.decimals();
  console.log(`\n📋 Allowance:`);
  console.log(`   Owner: ${owner}`);
  console.log(`   Spender: ${spender}`);
  console.log(`   Amount: ${formatAmount(allowance, decimals)} wRTC`);
}

async function burn(contract, amountStr) {
  if (!amountStr) {
    console.log("❌ Usage: burn <amount>");
    return;
  }
  
  const amount = parseAmount(amountStr, await contract.decimals());
  console.log(`\n🔥 Burning ${amountStr} wRTC...`);
  
  const tx = await contract.burn(amount);
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function addOperator(contract, operator) {
  if (!operator) {
    console.log("❌ Usage: add-operator <address>");
    return;
  }
  
  console.log(`\n➕ Adding bridge operator: ${operator}...`);
  
  const tx = await contract.addBridgeOperator(operator);
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function removeOperator(contract, operator) {
  if (!operator) {
    console.log("❌ Usage: remove-operator <address>");
    return;
  }
  
  console.log(`\n➖ Removing bridge operator: ${operator}...`);
  
  const tx = await contract.removeBridgeOperator(operator);
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function pause(contract) {
  console.log("\n⏸️  Pausing contract...");
  
  const tx = await contract.pause();
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function unpause(contract) {
  console.log("\n▶️  Unpausing contract...");
  
  const tx = await contract.unpause();
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function bridgeMint(contract, to, amountStr) {
  if (!to || !amountStr) {
    console.log("❌ Usage: bridge-mint <to> <amount>");
    return;
  }
  
  const amount = parseAmount(amountStr, await contract.decimals());
  console.log(`\n🌉 Bridge minting ${amountStr} wRTC to ${to}...`);
  
  const tx = await contract.bridgeMint(to, amount);
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

async function bridgeBurn(contract, from, amountStr) {
  if (!from || !amountStr) {
    console.log("❌ Usage: bridge-burn <from> <amount>");
    return;
  }
  
  const amount = parseAmount(amountStr, await contract.decimals());
  console.log(`\n🌉 Bridge burning ${amountStr} wRTC from ${from}...`);
  
  const tx = await contract.bridgeBurn(from, amount);
  console.log(`   Tx: ${tx.hash}`);
  
  const receipt = await tx.wait();
  console.log(`   ✅ Confirmed in block ${receipt.blockNumber}`);
}

function showHelp() {
  console.log(`
WRTC Contract Interaction Commands:

  node scripts/interact.js info                    - Show token info
  node scripts/interact.js balance [address]       - Check balance
  node scripts/interact.js transfer <to> <amount>  - Transfer tokens
  node scripts/interact.js approve <spender> <amt> - Approve spending
  node scripts/interact.js allowance <spender>     - Check allowance
  node scripts/interact.js burn <amount>           - Burn tokens
  node scripts/interact.js add-operator <addr>     - Add bridge operator
  node scripts/interact.js remove-operator <addr>  - Remove bridge operator
  node scripts/interact.js pause                   - Pause contract
  node scripts/interact.js unpause                 - Unpause contract
  node scripts/interact.js bridge-mint <to> <amt>  - Bridge mint (operator only)
  node scripts/interact.js bridge-burn <from> <amt>- Bridge burn (operator only)

Environment Variables:
  WRTC_ADDRESS - Contract address (required)
`);
}

function formatAmount(amount, decimals) {
  return (Number(amount) / Math.pow(10, Number(decimals))).toLocaleString();
}

function parseAmount(amountStr, decimals) {
  return ethers.parseUnits(amountStr, Number(decimals));
}

function getDeploymentAddress(chainId) {
  const fs = require("fs");
  const path = require("path");
  
  const networkName = chainId === 8453n ? "base" : 
                      chainId === 84532n ? "base-sepolia" : 
                      `chain-${chainId}`;
  
  const filePath = path.join(__dirname, "..", "artifacts", "deployments", `${networkName}-WRTC.json`);
  
  try {
    const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
    return data.contractAddress;
  } catch (e) {
    return null;
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
