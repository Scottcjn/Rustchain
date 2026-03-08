const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying wRTC with account:", deployer.address);
  console.log("Account balance:", (await deployer.provider.getBalance(deployer.address)).toString());

  const WrappedRTC = await hre.ethers.getContractFactory("WrappedRTC");
  const wrtc = await WrappedRTC.deploy(deployer.address);
  await wrtc.waitForDeployment();

  const address = await wrtc.getAddress();
  console.log("wRTC deployed to:", address);
  console.log("Owner:", await wrtc.owner());
  console.log("Total supply:", await wrtc.totalSupply());
  console.log("Max supply:", await wrtc.MAX_SUPPLY());
  console.log("Decimals:", await wrtc.decimals());
  
  console.log("\n✅ Deployment complete!");
  console.log(`Verify with: npx hardhat verify --network base-sepolia ${address} ${deployer.address}`);
  
  return address;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
