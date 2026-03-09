/**
 * Contract Verification Script
 * 
 * Verifies the WRTC contract on BaseScan
 * 
 * Usage:
 *   npx hardhat run scripts/verify.js --network base
 */

const hre = require("hardhat");

async function main() {
  console.log("=".repeat(60));
  console.log("RustChain wRTC Contract Verification");
  console.log("=".repeat(60));
  
  // Contract address from command line or environment
  const contractAddress = process.argv[2] || process.env.CONTRACT_ADDRESS;
  
  if (!contractAddress) {
    console.log("\n❌ ERROR: Contract address required");
    console.log("\nUsage:");
    console.log("  npx hardhat run scripts/verify.js --network base <CONTRACT_ADDRESS>");
    console.log("\nOr set CONTRACT_ADDRESS environment variable");
    process.exit(1);
  }
  
  // Deployment parameters (must match original deployment)
  const initialSupply = process.env.INITIAL_SUPPLY || "1000000";
  const bridgeOperator = process.env.BRIDGE_OPERATOR || "";
  
  console.log(`\n📋 Verification Details:`);
  console.log(`   Contract: ${contractAddress}`);
  console.log(`   Network: ${hre.network.name}`);
  console.log(`   Initial Supply: ${initialSupply}`);
  console.log(`   Bridge Operator: ${bridgeOperator || '(deployer)'}`);
  
  try {
    console.log("\n🔍 Verifying contract on BaseScan...");
    
    await hre.run("verify:verify", {
      address: contractAddress,
      constructorArguments: [
        hre.ethers.parseUnits(initialSupply, 6),
        bridgeOperator || (await hre.ethers.getSigners())[0].address,
      ],
    });
    
    console.log("\n✅ Contract verified successfully!");
    console.log(`   View on BaseScan: https://${hre.network.name === 'baseSepolia' ? 'sepolia.' : ''}basescan.org/address/${contractAddress}#code`);
    
  } catch (error) {
    if (error.message.includes("Already Verified")) {
      console.log("\nℹ️  Contract is already verified!");
    } else {
      console.log("\n❌ Verification failed:", error.message);
      console.log("\nManual verification instructions:");
      console.log("1. Go to https://basescan.org/address/" + contractAddress);
      console.log("2. Click 'Contract' tab > 'Verify and Publish'");
      console.log("3. Use these settings:");
      console.log("   - Compiler Type: Solidity (Single file)");
      console.log("   - Compiler Version: v0.8.20");
      console.log("   - Optimization: Yes (200 runs)");
      console.log("   - Constructor Arguments:");
      console.log(`     Initial Supply: ${hre.ethers.parseUnits(initialSupply, 6).toString()}`);
      console.log(`     Bridge Operator: ${bridgeOperator || '0x0000000000000000000000000000000000000000'}`);
    }
  }
  
  console.log("\n" + "=".repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
