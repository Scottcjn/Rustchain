/**
 * RustChain Epoch Reward Calculator
 * 
 * Calculate rewards for mining epochs on RustChain blockchain.
 * 
 * Base reward formula considers:
 * - Hardware fingerprint score (2.5x for vintage hardware)
 * - Block difficulty
 * - Epoch duration
 */

import axios from 'axios';

const API_BASE = 'https://rustchain.org';

// RustChain epoch parameters
const BASE_REWARD = 1.0; // Base RTC per block
const EPOCH_DURATION_BLOCKS = 1000;
const HARDWARE_BONUS_MULTIPLIER = 2.5; // Max for vintage hardware

interface EpochInfo {
  epoch: number;
  startBlock: number;
  endBlock: number;
  difficulty: number;
  totalRewards: number;
  minerCount: number;
}

interface HardwareScore {
  clockDrift: number;
  cacheTiming: number;
  simdIdentity: number;
  vmDetection: boolean;
  fingerprintScore: number;
}

/**
 * Calculate hardware bonus multiplier based on fingerprint score
 */
export function calculateHardwareBonus(score: number): number {
  // Score ranges from 0-100, bonus from 1.0 to 2.5
  return 1.0 + (score / 100) * (HARDWARE_BONUS_MULTIPLIER - 1.0);
}

/**
 * Calculate epoch reward for a miner
 */
export function calculateEpochReward(
  blocksMined: number,
  hardwareScore: number,
  difficulty: number = 1.0
): number {
  const hardwareBonus = calculateHardwareBonus(hardwareScore);
  const baseReward = blocksMined * BASE_REWARD;
  const difficultyFactor = 1 / difficulty;
  
  return baseReward * hardwareBonus * difficultyFactor;
}

/**
 * Get current epoch info from API
 */
export async function getCurrentEpoch(): Promise<EpochInfo | null> {
  try {
    const response = await axios.get(`${API_BASE}/epoch`);
    return response.data;
  } catch (error) {
    console.error('Failed to fetch epoch info:', error);
    return null;
  }
}

/**
 * Estimate time to reach target reward
 */
export function estimateTimeToReward(
  hashrate: number, // blocks per hour
  hardwareScore: number,
  targetReward: number,
  difficulty: number = 1.0
): number {
  let accumulatedReward = 0;
  let hours = 0;
  
  while (accumulatedReward < targetReward) {
    accumulatedReward += calculateEpochReward(hashrate, hardwareScore, difficulty) / 3600; // per second
    hours++;
    if (hours > 1000000) break; // Safety limit
  }
  
  return hours;
}

/**
 * Format time duration
 */
export function formatDuration(hours: number): string {
  if (hours < 1) {
    return `${Math.round(hours * 60)} minutes`;
  } else if (hours < 24) {
    return `${hours.toFixed(1)} hours`;
  } else {
    const days = hours / 24;
    return `${days.toFixed(1)} days`;
  }
}

// CLI Interface
import { Command } from 'commander';
import chalk from 'chalk';

const program = new Command();

program
  .name('rustchain-epoch')
  .description('RustChain Epoch Reward Calculator')
  .version('1.0.0');

program
  .command('calculate')
  .description('Calculate epoch reward')
  .requiredOption('-b, --blocks <number>', 'Number of blocks mined')
  .requiredOption('-s, --score <number>', 'Hardware fingerprint score (0-100)')
  .option('-d, --difficulty <number>', 'Network difficulty', '1.0')
  .action((options) => {
    const blocks = parseInt(options.blocks);
    const score = parseInt(options.score);
    const difficulty = parseFloat(options.difficulty);
    
    const reward = calculateEpochReward(blocks, score, difficulty);
    const bonus = calculateHardwareBonus(score);
    
    console.log(chalk.blue('\n📊 Epoch Reward Calculation\n'));
    console.log(chalk.cyan('Blocks Mined:'), blocks);
    console.log(chalk.cyan('Hardware Score:'), score);
    console.log(chalk.cyan('Difficulty:'), difficulty);
    console.log(chalk.cyan('Hardware Bonus:'), `${bonus.toFixed(2)}x`);
    console.log(chalk.green('\n💰 Estimated Reward:'), `${reward.toFixed(4)} RTC`);
    console.log('');
  });

program
  .command('info')
  .description('Get current epoch info')
  .action(async () => {
    console.log(chalk.blue('\n📡 Fetching epoch info...\n'));
    const epoch = await getCurrentEpoch();
    
    if (epoch) {
      console.log(chalk.cyan('Epoch:'), epoch.epoch);
      console.log(chalk.cyan('Start Block:'), epoch.startBlock);
      console.log(chalk.cyan('End Block:'), epoch.endBlock);
      console.log(chalk.cyan('Difficulty:'), epoch.difficulty);
      console.log(chalk.cyan('Total Rewards:'), epoch.totalRewards);
      console.log(chalk.cyan('Miners:'), epoch.minerCount);
    } else {
      console.log(chalk.red('Failed to fetch epoch info'));
    }
    console.log('');
  });

program
  .command('estimate')
  .description('Estimate time to reach target reward')
  .requiredOption('-r, --reward <number>', 'Target reward (RTC)')
  .requiredOption('-h, --hashrate <number>', 'Hashrate (blocks per hour)')
  .requiredOption('-s, --score <number>', 'Hardware fingerprint score (0-100)')
  .option('-d, --difficulty <number>', 'Network difficulty', '1.0')
  .action((options) => {
    const reward = parseFloat(options.reward);
    const hashrate = parseFloat(options.hashrate);
    const score = parseInt(options.score);
    const difficulty = parseFloat(options.difficulty);
    
    const hours = estimateTimeToReward(hashrate, score, reward, difficulty);
    
    console.log(chalk.blue('\n⏱️ Time Estimation\n'));
    console.log(chalk.cyan('Target Reward:'), `${reward} RTC`);
    console.log(chalk.cyan('Hashrate:'), `${hashrate} blocks/hour`);
    console.log(chalk.cyan('Hardware Score:'), score);
    console.log(chalk.cyan('Difficulty:'), difficulty);
    console.log(chalk.green('\n⏰ Estimated Time:'), formatDuration(hours));
    console.log('');
  });

program.parse();
