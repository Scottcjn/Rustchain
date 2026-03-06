/**
 * RustChain Agent Economy Discord Bot
 * 
 * A Discord bot that mirrors the RustChain Agent Economy marketplace,
 * allowing users to browse, post, claim, and manage jobs directly from Discord.
 * 
 * Features:
 * - Browse open jobs
 * - Post new jobs
 * - Claim jobs
 * - Check reputation
 * - Market statistics
 * 
 * Required Environment Variables:
 * - DISCORD_BOT_TOKEN: Your Discord bot token
 * - RUSTCHAIN_API_URL: RustChain API base URL (default: https://rustchain.org)
 */

import { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, StringSelectMenuBuilder, StringSelectMenuOptionBuilder } from 'discord.js';
import axios from 'axios';

// Configuration
const API_BASE = process.env.RUSTCHAIN_API_URL || 'https://rustchain.org';

// Initialize Discord Client
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.DirectMessages,
  ],
});

// API Helper Functions
async function getMarketStats() {
  try {
    const response = await axios.get(`${API_BASE}/agent/stats`);
    return response.data;
  } catch (error) {
    console.error('Error fetching stats:', error);
    return null;
  }
}

async function getJobs(category?: string, limit: number = 10) {
  try {
    const params: any = { limit };
    if (category) params.category = category;
    const response = await axios.get(`${API_BASE}/agent/jobs`, { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching jobs:', error);
    return [];
  }
}

async function getJob(jobId: string) {
  try {
    const response = await axios.get(`${API_BASE}/agent/jobs/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching job:', error);
    return null;
  }
}

async function getReputation(wallet: string) {
  try {
    const response = await axios.get(`${API_BASE}/agent/reputation/${wallet}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching reputation:', error);
    return null;
  }
}

async function postJob(data: any) {
  try {
    const response = await axios.post(`${API_BASE}/agent/jobs`, data);
    return response.data;
  } catch (error: any) {
    console.error('Error posting job:', error);
    return { error: error.response?.data?.message || error.message };
  }
}

// Command Handlers
async function handleStats(interaction: any) {
  const stats = await getMarketStats();
  
  if (!stats) {
    await interaction.reply({ content: 'Failed to fetch market statistics.', ephemeral: true });
    return;
  }
  
  const embed = new EmbedBuilder()
    .setTitle('📊 RustChain Agent Economy Statistics')
    .setColor(0x00ff00)
    .addFields(
      { name: 'Total Jobs', value: `${stats.total_jobs || 0}`, inline: true },
      { name: 'Open Jobs', value: `${stats.open_jobs || 0}`, inline: true },
      { name: 'Completed', value: `${stats.completed_jobs || 0}`, inline: true },
      { name: 'RTC Locked', value: `${stats.total_rtc_locked || 0}`, inline: true },
      { name: 'Average Reward', value: `${stats.average_reward || 0} RTC`, inline: true }
    )
    .setTimestamp();
  
  if (stats.top_categories?.length) {
    const categories = stats.top_categories.map((c: any) => `${c.category}: ${c.count}`).join('\n');
    embed.addFields({ name: 'Top Categories', value: categories });
  }
  
  await interaction.reply({ embeds: [embed] });
}

async function handleJobs(interaction: any, category?: string) {
  const jobs = await getJobs(category, 10);
  
  if (!jobs || jobs.length === 0) {
    await interaction.reply({ content: 'No jobs found.', ephemeral: true });
    return;
  }
  
  const embed = new EmbedBuilder()
    .setTitle('💼 Open Jobs')
    .setColor(0x0099ff)
    .setTimestamp();
  
  for (const job of jobs.slice(0, 10)) {
    embed.addFields({
      name: `${job.title}`,
      value: `Reward: ${job.reward_rtc} RTC | Category: ${job.category}\nID: \`${job.id}\``,
      inline: false
    });
  }
  
  await interaction.reply({ embeds: [embed] });
}

async function handleJobDetails(interaction: any, jobId: string) {
  const job = await getJob(jobId);
  
  if (!job) {
    await interaction.reply({ content: 'Job not found.', ephemeral: true });
    return;
  }
  
  const embed = new EmbedBuilder()
    .setTitle(`📋 ${job.title}`)
    .setColor(0x00ff00)
    .setDescription(job.description)
    .addFields(
      { name: 'Reward', value: `${job.reward_rtc} RTC`, inline: true },
      { name: 'Category', value: job.category, inline: true },
      { name: 'Status', value: job.status || 'open', inline: true },
      { name: 'Poster', value: job.poster_wallet, inline: true }
    )
    .setTimestamp();
  
  if (job.tags?.length) {
    embed.addFields({ name: 'Tags', value: job.tags.join(', ') });
  }
  
  const row = new ActionRowBuilder<ButtonBuilder>()
    .addComponents(
      new ButtonBuilder()
        .setCustomId(`claim_${job.id}`)
        .setLabel('Claim Job')
        .setStyle(ButtonStyle.Primary)
    );
  
  await interaction.reply({ embeds: [embed], components: [row] });
}

async function handleReputation(interaction: any, wallet: string) {
  const rep = await getReputation(wallet);
  
  if (!rep) {
    await interaction.reply({ content: 'Wallet not found or no reputation data.', ephemeral: true });
    return;
  }
  
  const embed = new EmbedBuilder()
    .setTitle(`⭐ Reputation: ${wallet}`)
    .setColor(0xffaa00)
    .addFields(
      { name: 'Trust Score', value: `${rep.trust_score || 0}`, inline: true },
      { name: 'Trust Level', value: rep.trust_level || 'newcomer', inline: true },
      { name: 'Total Jobs', value: `${rep.total_jobs || 0}`, inline: true },
      { name: 'Completed', value: `${rep.completed_jobs || 0}`, inline: true },
      { name: 'Disputed', value: `${rep.disputed_jobs || 0}`, inline: true },
      { name: 'Average Rating', value: `${rep.avg_rating || 'N/A'}`, inline: true }
    )
    .setTimestamp();
  
  await interaction.reply({ embeds: [embed] });
}

// Slash Commands Setup
const commands = [
  {
    name: 'stats',
    description: 'Show Agent Economy market statistics',
  },
  {
    name: 'jobs',
    description: 'Browse open jobs',
    options: [
      {
        name: 'category',
        description: 'Filter by category',
        type: 3,
        required: false,
        choices: [
          { name: 'Research', value: 'research' },
          { name: 'Code', value: 'code' },
          { name: 'Video', value: 'video' },
          { name: 'Audio', value: 'audio' },
          { name: 'Writing', value: 'writing' },
          { name: 'Translation', value: 'translation' },
          { name: 'Data', value: 'data' },
          { name: 'Design', value: 'design' },
          { name: 'Testing', value: 'testing' },
          { name: 'Other', value: 'other' },
        ],
      },
    ],
  },
  {
    name: 'job',
    description: 'Get job details',
    options: [
      {
        name: 'job_id',
        description: 'The job ID',
        type: 3,
        required: true,
      },
    ],
  },
  {
    name: 'reputation',
    description: 'Check wallet reputation',
    options: [
      {
        name: 'wallet',
        description: 'Wallet address or name',
        type: 3,
        required: true,
      },
    ],
  },
  {
    name: 'help',
    description: 'Show help information',
  },
];

// Event Listeners
client.on('ready', async () => {
  console.log(`Logged in as ${client.user?.tag}!`);
  
  // Register slash commands
  try {
    await client.application?.commands.set(commands);
    console.log('Slash commands registered!');
  } catch (error) {
    console.error('Error registering commands:', error);
  }
});

client.on('interactionCreate', async (interaction: any) => {
  if (!interaction.isCommand()) return;
  
  const { commandName, options } = interaction;
  
  switch (commandName) {
    case 'stats':
      await handleStats(interaction);
      break;
      
    case 'jobs':
      const category = options.getString('category');
      await handleJobs(interaction, category);
      break;
      
    case 'job':
      const jobId = options.getString('job_id');
      await handleJobDetails(interaction, jobId);
      break;
      
    case 'reputation':
      const wallet = options.getString('wallet');
      await handleReputation(interaction, wallet);
      break;
      
    case 'help':
      const helpEmbed = new EmbedBuilder()
        .setTitle('🤖 RustChain Agent Economy Bot')
        .setColor(0x00ff00)
        .setDescription('Discord bot for the RustChain Agent Economy marketplace')
        .addFields(
          { name: '/stats', value: 'View market statistics', inline: true },
          { name: '/jobs', value: 'Browse open jobs', inline: true },
          { name: '/jobs --category', value: 'Filter jobs by category', inline: true },
          { name: '/job <id>', value: 'Get job details', inline: true },
          { name: '/reputation <wallet>', value: 'Check agent reputation', inline: true },
          { name: '/help', value: 'Show this help message', inline: true }
        )
        .setTimestamp();
      await interaction.reply({ embeds: [helpEmbed] });
      break;
  }
});

// Handle button interactions
client.on('interactionCreate', async (interaction: any) => {
  if (!interaction.isButton()) return;
  
  const customId = interaction.customId;
  
  if (customId.startsWith('claim_')) {
    const jobId = customId.replace('claim_', '');
    await interaction.reply({ 
      content: `To claim job ${jobId}, use the Agent Economy API or CLI tool.\n\nClaim command:\n\`\`\`\ncurl -X POST ${API_BASE}/agent/jobs/${jobId}/claim -H "Content-Type: application/json" -d '{"worker_wallet":"YOUR_WALLET"}'\n\`\`\``,
      ephemeral: true 
    });
  }
});

// Start the bot
const TOKEN = process.env.DISCORD_BOT_TOKEN;

if (!TOKEN) {
  console.log('Please set DISCORD_BOT_TOKEN environment variable to start the bot.');
  console.log('Example: DISCORD_BOT_TOKEN=your_token node dist/index.js');
  process.exit(0);
} else {
  client.login(TOKEN);
}

export { client, getMarketStats, getJobs, getJob, getReputation, postJob };
