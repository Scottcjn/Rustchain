const { ethers } = require("hardhat");

async function main() {
  const WRTC = await ethers.getContractFactory("WRTC");
  const wrtc = await WRTC.deploy();
  await wrtc.waitForDeployment();
  console.log("wRTC deployed to:", await wrtc.getAddress());
}

main().catch(console.error);
