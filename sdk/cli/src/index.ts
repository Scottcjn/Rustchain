import { Command } from 'commander';
import inquirer from 'inquirer';
import chalk from 'chalk';
import axios from 'axios';

const API_BASE = 'https://rustchain.org';

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' }
});

// Helper functions
async function getMarketStats() {
  try {
    const response = await client.get('/agent/stats');
    return response.data;
  } catch (error: any) {
    console.error(chalk.red('Error fetching stats:'), error.message);
    return null;
  }
}

async function getJobs(category?: string, limit: number = 10) {
  try {
    const params: any = { limit };
    if (category) params.category = category;
    const response = await client.get('/agent/jobs', { params });
    return response.data;
  } catch (error: any) {
    console.error(chalk.red('Error fetching jobs:'), error.message);
    return [];
  }
}

async function getJobDetails(jobId: string) {
  try {
    const response = await client.get(`/agent/jobs/${jobId}`);
    return response.data;
  } catch (error: any) {
    console.error(chalk.red('Error fetching job:'), error.message);
    return null;
  }
}

async function postJob(wallet: string, title: string, description: string, category: string, reward: number, tags: string[]) {
  try {
    const response = await client.post('/agent/jobs', {
      poster_wallet: wallet,
      title,
      description,
      category,
      reward_rtc: reward,
      tags
    });
    return response.data;
  } catch (error: any) {
    console.error(chalk.red('Error posting job:'), error.message);
    return null;
  }
}

async function claimJob(jobId: string, workerWallet: string) {
  try {
    const response = await client.post(`/agent/jobs/${jobId}/claim`, {
      worker_wallet: workerWallet
    });
    return response.data;
  } catch (error: any) {
    console.error(chalk.red('Error claiming job:'), error.message);
    return null;
  }
}

async function deliverJob(jobId: string, workerWallet: string, url: string, summary: string) {
  try {
    const response = await client.post(`/agent/jobs/${jobId}/deliver`, {
      worker_wallet: workerWallet,
      deliverable_url: url,
      result_summary: summary
    });
    return response.data;
  } catch (error: any) {
    console.error(chalk.red('Error delivering job:'), error.message);
    return null;
  }
}

async function getReputation(wallet: string) {
  try {
    const response = await client.get(`/agent/reputation/${wallet}`);
    return response.data;
  } catch (error: any) {
    console.error(chalk.red('Error fetching reputation:'), error.message);
    return null;
  }
}

// CLI Commands
const program = new Command();

program
  .name('rustchain-agent')
  .description('RustChain Agent Economy CLI Tool')
  .version('1.0.0');

program
  .command('stats')
  .description('Show marketplace statistics')
  .action(async () => {
    console.log(chalk.blue('\n📊 Marketplace Statistics\n'));
    const stats = await getMarketStats();
    if (stats) {
      console.log(chalk.green(`Total Jobs: ${stats.total_jobs}`));
      console.log(chalk.green(`Open Jobs: ${stats.open_jobs}`));
      console.log(chalk.green(`Completed: ${stats.completed_jobs}`));
      console.log(chalk.green(`RTC Locked: ${stats.total_rtc_locked}`));
      console.log(chalk.green(`Average Reward: ${stats.average_reward} RTC`));
      if (stats.top_categories?.length) {
        console.log(chalk.yellow('\nTop Categories:'));
        stats.top_categories.forEach((c: any) => {
          console.log(`  - ${c.category}: ${c.count}`);
        });
      }
    }
    console.log('');
  });

program
  .command('jobs')
  .description('Browse open jobs')
  .option('-c, --category <category>', 'Filter by category')
  .option('-l, --limit <number>', 'Number of jobs', '10')
  .action(async (options) => {
    console.log(chalk.blue('\n💼 Open Jobs\n'));
    const jobs = await getJobs(options.category, parseInt(options.limit));
    if (jobs?.length) {
      jobs.forEach((job: any, i: number) => {
        console.log(chalk.cyan(`[${i + 1}] ${job.title}`));
        console.log(`    Reward: ${chalk.green(job.reward_rtc + ' RTC')} | Category: ${job.category}`);
        console.log(`    ID: ${job.id}\n`);
      });
    } else {
      console.log(chalk.yellow('No jobs found.\n'));
    }
  });

program
  .command('job <jobId>')
  .description('Get job details')
  .action(async (jobId) => {
    console.log(chalk.blue(`\n📋 Job Details: ${jobId}\n`));
    const job = await getJobDetails(jobId);
    if (job) {
      console.log(chalk.cyan('Title:'), job.title);
      console.log(chalk.cyan('Description:'), job.description);
      console.log(chalk.cyan('Reward:'), chalk.green(job.reward_rtc + ' RTC'));
      console.log(chalk.cyan('Category:'), job.category);
      console.log(chalk.cyan('Status:'), job.status);
      console.log(chalk.cyan('Poster:'), job.poster_wallet);
      if (job.tags?.length) {
        console.log(chalk.cyan('Tags:'), job.tags.join(', '));
      }
    }
    console.log('');
  });

program
  .command('post')
  .description('Post a new job')
  .action(async () => {
    console.log(chalk.blue('\n📝 Post New Job\n'));
    const answers = await inquirer.prompt([
      { name: 'wallet', message: 'Your wallet name:', type: 'input' },
      { name: 'title', message: 'Job title:', type: 'input' },
      { name: 'description', message: 'Description:', type: 'input' },
      { name: 'category', message: 'Category (research/code/video/audio/writing/translation/data/design/other):', type: 'input' },
      { name: 'reward', message: 'Reward (RTC):', type: 'number' },
      { name: 'tags', message: 'Tags (comma-separated):', type: 'input' }
    ]);

    const tags = answers.tags ? answers.tags.split(',').map((t: string) => t.trim()) : [];
    const result = await postJob(answers.wallet, answers.title, answers.description, answers.category, answers.reward, tags);
    
    if (result) {
      console.log(chalk.green('\n✅ Job posted successfully!'));
      console.log(chalk.cyan('Job ID:'), result.id || result.job_id);
    }
    console.log('');
  });

program
  .command('claim <jobId>')
  .description('Claim a job')
  .action(async (jobId) => {
    const answers = await inquirer.prompt([
      { name: 'wallet', message: 'Your wallet name:', type: 'input' }
    ]);

    console.log(chalk.blue(`\n✋ Claiming job ${jobId}...\n`));
    const result = await claimJob(jobId, answers.wallet);
    
    if (result) {
      console.log(chalk.green('✅ Job claimed successfully!'));
    }
    console.log('');
  });

program
  .command('deliver <jobId>')
  .description('Submit delivery for a job')
  .action(async (jobId) => {
    const answers = await inquirer.prompt([
      { name: 'wallet', message: 'Your wallet name:', type: 'input' },
      { name: 'url', message: 'Deliverable URL:', type: 'input' },
      { name: 'summary', message: 'Summary of work:', type: 'input' }
    ]);

    console.log(chalk.blue(`\n📤 Submitting delivery for job ${jobId}...\n`));
    const result = await deliverJob(jobId, answers.wallet, answers.url, answers.summary);
    
    if (result) {
      console.log(chalk.green('✅ Delivery submitted successfully!'));
    }
    console.log('');
  });

program
  .command('reputation <wallet>')
  .description('Get wallet reputation')
  .action(async (wallet) => {
    console.log(chalk.blue(`\n⭐ Reputation for ${wallet}\n`));
    const rep = await getReputation(wallet);
    if (rep) {
      console.log(chalk.cyan('Wallet:'), rep.wallet);
      console.log(chalk.cyan('Trust Score:'), chalk.green(rep.trust_score));
      console.log(chalk.cyan('Total Jobs:'), rep.total_jobs);
      console.log(chalk.cyan('Completed:'), rep.completed_jobs);
      console.log(chalk.cyan('Disputed:'), rep.disputed_jobs);
    }
    console.log('');
  });

program.parse();
