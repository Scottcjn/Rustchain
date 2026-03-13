/**
 * RustChain Telegram Bot 测试脚本
 * 
 * 用于测试区块链连接和基本功能，无需启动完整的机器人
 */

require('dotenv').config();
const { ethers } = require('ethers');

const RPC_URL = process.env.RUSTCHAIN_RPC_URL || 'https://rpc.rustchain.io';
const WATCHED_WALLET = process.env.WATCHED_WALLET || 'RTC4325af95d26d59c3ef025963656d22af638bb96b';

async function testConnection() {
  console.log('🔍 开始测试 RustChain 连接...\n');
  
  try {
    // 测试连接
    console.log('1️⃣ 测试 RPC 连接...');
    const provider = new ethers.JsonRpcProvider(RPC_URL);
    
    // 获取网络信息
    console.log('2️⃣ 获取网络信息...');
    const network = await provider.getNetwork();
    console.log(`   ✅ 网络 ID: ${network.chainId}`);
    
    // 获取最新区块
    console.log('3️⃣ 获取最新区块...');
    const blockNumber = await provider.getBlockNumber();
    console.log(`   ✅ 区块高度：${blockNumber}`);
    
    // 获取 Gas 价格
    console.log('4️⃣ 获取 Gas 价格...');
    const feeData = await provider.getFeeData();
    const gasPrice = ethers.formatUnits(feeData.gasPrice || 0, 'gwei');
    console.log(`   ✅ Gas 价格：${parseFloat(gasPrice).toFixed(2)} Gwei`);
    
    // 获取钱包余额
    console.log('5️⃣ 查询钱包余额...');
    console.log(`   钱包地址：${WATCHED_WALLET}`);
    const balance = await provider.getBalance(WATCHED_WALLET);
    const balanceInEther = ethers.formatEther(balance);
    console.log(`   ✅ 余额：${parseFloat(balanceInEther).toFixed(6)} RTC`);
    
    // 获取钱包交易计数
    console.log('6️⃣ 查询交易计数...');
    const txCount = await provider.getTransactionCount(WATCHED_WALLET);
    console.log(`   ✅ 交易计数：${txCount}`);
    
    console.log('\n✅ 所有测试通过！区块链连接正常。\n');
    
    return {
      success: true,
      network: network.chainId,
      blockNumber,
      gasPrice: parseFloat(gasPrice).toFixed(2),
      balance: parseFloat(balanceInEther).toFixed(6),
      txCount
    };
    
  } catch (error) {
    console.error('\n❌ 测试失败！');
    console.error(`错误信息：${error.message}`);
    console.error('\n可能的原因:');
    console.error('1. RPC 节点不可用');
    console.error('2. 网络连接问题');
    console.error('3. 钱包地址格式不正确');
    console.error('\n请检查配置后重试。\n');
    
    return {
      success: false,
      error: error.message
    };
  }
}

// 运行测试
console.log('='.repeat(60));
console.log('RustChain Telegram Bot - 连接测试');
console.log('='.repeat(60));
console.log('');

testConnection().then(result => {
  if (result.success) {
    console.log('📊 测试结果汇总:');
    console.log('─'.repeat(60));
    console.log(`网络 ID:      ${result.network}`);
    console.log(`区块高度：    ${result.blockNumber}`);
    console.log(`Gas 价格：    ${result.gasPrice} Gwei`);
    console.log(`钱包余额：    ${result.balance} RTC`);
    console.log(`交易计数：    ${result.txCount}`);
    console.log('─'.repeat(60));
    console.log('');
    console.log('✅ 机器人已准备就绪！可以启动使用。\n');
  } else {
    console.log('⚠️  测试失败，但机器人仍可启动（可能会显示错误）。\n');
  }
  
  process.exit(result.success ? 0 : 1);
});
