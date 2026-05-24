// SPDX-License-Identifier: MIT

const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  const initialMinter = process.env.NFT_MINTER || ethers.ZeroAddress;

  console.log("Deploying RustChainNFT with account:", deployer.address);
  console.log("Initial NFT minter:", initialMinter);

  const RustChainNFT = await ethers.getContractFactory("RustChainNFT");
  const nft = await RustChainNFT.deploy(initialMinter);
  await nft.waitForDeployment();

  console.log("RustChainNFT deployed to:", await nft.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
