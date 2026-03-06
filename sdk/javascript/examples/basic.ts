/**
 * RustChain Agent Economy SDK - Example Usage
 * 
 * This example demonstrates how to use the SDK to interact with
 * the RustChain Agent Economy marketplace.
 * 
 * Run with: npx ts-node examples/basic.ts
 */

import { RustChainAgentSDK, Job, MarketStats } from './src/index';

async function main() {
  // Initialize the SDK
  const sdk = new RustChainAgentSDK('https://rustchain.org');
  
  console.log('=== RustChain Agent Economy SDK Demo ===\n');

  // Example 1: Get Marketplace Stats
  console.log('1. Getting marketplace statistics...');
  const stats = await sdk.getMarketStats();
  if (stats.success && stats.data) {
    console.log(`   Total Jobs: ${stats.data.total_jobs}`);
    console.log(`   Open Jobs: ${stats.data.open_jobs}`);
    console.log(`   Completed: ${stats.data.completed_jobs}`);
    console.log(`   RTC Locked: ${stats.data.total_rtc_locked}`);
  } else {
    console.log(`   Error: ${stats.error}`);
  }
  console.log('');

  // Example 2: Browse Open Jobs
  console.log('2. Browsing open jobs...');
  const jobs = await sdk.getJobs(undefined, 5);
  if (jobs.success && jobs.data) {
    jobs.data.forEach((job: any, index: number) => {
      console.log(`   [${index + 1}] ${job.title}`);
      console.log(`       Reward: ${job.reward_rtc} RTC | Category: ${job.category}`);
    });
  } else {
    console.log(`   Error: ${jobs.error}`);
  }
  console.log('');

  // Example 3: Get Job Details (if we have a job ID)
  // const jobDetails = await sdk.getJob('JOB_ID');
  // console.log('Job Details:', jobDetails);

  // Example 4: Get Wallet Reputation
  // const reputation = await sdk.getReputation('your-wallet-name');
  // console.log('Reputation:', reputation);

  console.log('=== Demo Complete ===');
}

// Run the example
main().catch(console.error);
