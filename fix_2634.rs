// botTubeAgentMatcher.js
const { ethers } = require('ethers');
const axios = require('axios');

class BotTubeAgentMatcher {
  constructor(providerUrl, contractAddress, privateKey) {
    this.provider = new ethers.providers.JsonRpcProvider(providerUrl);
    this.wallet = new ethers.Wallet(privateKey, this.provider);
    this.contract = new ethers.Contract(
      contractAddress,
      [
        'function registerHuman(address agent, address human) external',
        'function verifyEngagement(address agent) external view returns (bool)',
        'function claimReward(address agent) external'
      ],
      this.wallet
    );
    this.apiBase = 'https://api.bottube.elyanlabs.io/v1';
  }

  async checkAgentActivity(agentAddress) {
    try {
      const [stars, follows, uploads, comments] = await Promise.all([
        axios.get(`${this.apiBase}/agents/${agentAddress}/stars`),
        axios.get(`${this.apiBase}/agents/${agentAddress}/follows`),
        axios.get(`${this.apiBase}/agents/${agentAddress}/uploads`),
        axios.get(`${this.apiBase}/agents/${agentAddress}/comments`)
      ]);

      return {
        isActive: stars.data.count > 0 || follows.data.count > 0 || 
                  uploads.data.count > 0 || comments.data.count > 0,
        metrics: {
          stars: stars.data.count,
          follows: follows.data.count,
          uploads: uploads.data.count,
          comments: comments.data.count
        }
      };
    } catch (error) {
      console.error('Error checking agent activity:', error);
      return { isActive: false, metrics: {} };
    }
  }

  async registerHumanForAgent(agentAddress, humanAddress) {
    const activity = await this.checkAgentActivity(agentAddress);
    
    if (!activity.isActive) {
      throw new Error('Agent must have at least one engagement metric');
    }

    const tx = await this.contract.registerHuman(agentAddress, humanAddress);
    await tx.wait();
    
    return {
      success: true,
      transactionHash: tx.hash,
      agentAddress,
      humanAddress,
      agentMetrics: activity.metrics
    };
  }

  async verifyAndClaim(agentAddress) {
    const isVerified = await this.contract.verifyEngagement(agentAddress);
    
    if (!isVerified) {
      throw new Error('Agent engagement not verified');
    }

    const tx = await this.contract.claimReward(agentAddress);
    await tx.wait();
    
    return {
      success: true,
      transactionHash: tx.hash,
      rewardClaimed: true
    };
  }

  async getPoolStatus() {
    try {
      const response = await axios.get(`${this.apiBase}/campaigns/human-work-day`);
      return {
        totalPool: response.data.pool,
        remainingPool: response.data.remainingPool,
        registeredHumans: response.data.registeredHumans,
        registeredAgents: response.data.registeredAgents,
        daysRemaining: response.data.daysRemaining
      };
    } catch (error) {
      console.error('Error fetching pool status:', error);
      return null;
    }
  }
}

// Usage example
async function main() {
  const matcher = new BotTubeAgentMatcher(
    'https://rpc.rustchain.io',
    '0xYourContractAddress',
    '0xYourPrivateKey'
  );

  // Check pool status
  const poolStatus = await matcher.getPoolStatus();
  console.log('Pool Status:', poolStatus);

  // Register human for agent
  const agentAddress = '0xAgentAddress';
  const humanAddress = '0xHumanAddress';
  
  try {
    const registration = await matcher.registerHumanForAgent(agentAddress, humanAddress);
    console.log('Registration successful:', registration);
    
    // Verify and claim reward
    const claim = await matcher.verifyAndClaim(agentAddress);
    console.log('Reward claimed:', claim);
  } catch (error) {
    console.error('Error:', error.message);
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(console.error);
}

module.exports = BotTubeAgentMatcher;
