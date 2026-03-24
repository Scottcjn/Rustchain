require("@nomicfoundation/hardhat-toolbox");
require("hardhat-gas-reporter");
require("solidity-coverage");

require("dotenv").config();

/**
 * Hardhat Configuration for RustChain wRTC ERC-20
 * 
 * Networks:
 * - base: Base mainnet (eip155:8453)
 * - baseSepolia: Base testnet
 * - localhost: Local development
 * 
 * Environment variables required (create .env file):
 * - PRIVATE_KEY: Deployer private key
 * - ETHERSCAN_API_KEY: For verification (BaseScan)
 * - BASE_RPC_URL: Optional custom RPC
 */

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x" + "0".repeat(64);
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "";
const BASE_RPC_URL = process.env.BASE_RPC_URL || "https://mainnet.base.org";
const BASE_SEPOLIA_RPC_URL = process.env.BASE_SEPOLIA_RPC_URL || "https://sepolia.base.org";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.25",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      viaIR: false,
      evmVersion: "cancun",
    },
  },
  
  networks: {
    hardhat: {
      chainId: 31337,
      gas: 12000000,
      blockGasLimit: 12000000,
    },
    
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
    
    base: {
      url: BASE_RPC_URL,
      chainId: 8453,
      accounts: [PRIVATE_KEY],
      gasPrice: 1000000000, // 1 gwei
      timeout: 180000,
    },
    
    baseSepolia: {
      url: BASE_SEPOLIA_RPC_URL,
      chainId: 84532,
      accounts: [PRIVATE_KEY],
      gasPrice: 1000000000,
      timeout: 180000,
    },
  },
  
  etherscan: {
    apiKey: {
      base: ETHERSCAN_API_KEY,
      baseSepolia: ETHERSCAN_API_KEY,
    },
    customChains: [
      {
        network: "base",
        chainId: 8453,
        urls: {
          apiURL: "https://api.basescan.org/api",
          browserURL: "https://basescan.org",
        },
      },
      {
        network: "baseSepolia",
        chainId: 84532,
        urls: {
          apiURL: "https://api-sepolia.basescan.org/api",
          browserURL: "https://sepolia.basescan.org",
        },
      },
    ],
  },
  
  gasReporter: {
    enabled: process.env.REPORT_GAS === "true",
    currency: "USD",
    gasPrice: 50,
    coinmarketcap: process.env.COINMARKETCAP_API_KEY,
    excludeContracts: ["@openzeppelin/"],
  },
  
  mocha: {
    timeout: 100000,
  },
  
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
