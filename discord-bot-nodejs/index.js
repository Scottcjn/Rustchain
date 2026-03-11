/**
 * RustChain Discord Bot
 * Queries RustChain API and provides blockchain info via Discord commands
 * 
 * Commands:
 *  /balance - Check account balance
 *  /miners  - View miner information
 *  /epoch   - Current epoch status
 *  /health  - Node health status
 *  /tip     - Tip other users (bonus feature)
 */

require('dotenv').config();
const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder } = require('discord.js');
const axios = require('axios');

// Initialize Discord client
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

// RustChain API client
const api = axios.create({
    baseURL: process.env.RUSTCHAIN_API_URL || 'https://api.rustchain.org',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
        ...(process.env.RUSTCHAIN_API_KEY && { 'Authorization': `Bearer ${process.env.RUSTCHAIN_API_KEY}` })
    }
});

// Command registry
const commands = [];

// Load commands
const commandFiles = ['balance', 'miners', 'epoch', 'health', 'tip'];
for (const file of commandFiles) {
    try {
        const cmd = require(`./commands/${file}`);
        if (cmd.data && cmd.execute) {
            commands.push(cmd.data);
            console.log(`✓ Loaded command: ${cmd.data.name}`);
        }
    } catch (error) {
        console.error(`✗ Failed to load command ${file}:`, error.message);
    }
}

// Register slash commands
async function registerCommands() {
    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
    
    try {
        console.log('Started refreshing application (/) commands.');
        
        await rest.put(
            Routes.applicationCommands(process.env.DISCORD_CLIENT_ID),
            { body: commands.map(cmd => cmd.toJSON()) }
        );
        
        console.log('Successfully reloaded application (/) commands.');
    } catch (error) {
        console.error('Error registering commands:', error);
    }
}

// Bot ready event
client.once('ready', async () => {
    console.log(`✓ Bot logged in as ${client.user.tag}`);
    console.log(`✓ Connected to ${client.guilds.cache.size} guild(s)`);
    
    // Register commands
    await registerCommands();
    
    // Set bot status
    client.user.setPresence({
        activities: [{ name: 'RustChain | /help' }],
        status: 'online'
    });
});

// Interaction handler
client.on('interactionCreate', async interaction => {
    if (!interaction.isChatInputCommand()) return;
    
    const commandName = interaction.commandName;
    
    try {
        const cmd = require(`./commands/${commandName}`);
        await cmd.execute(interaction, api);
    } catch (error) {
        console.error(`Error executing ${commandName}:`, error);
        
        const errorMessage = {
            content: '❌ An error occurred while executing this command.',
            ephemeral: true
        };
        
        if (interaction.replied || interaction.deferred) {
            await interaction.followUp(errorMessage);
        } else {
            await interaction.reply(errorMessage);
        }
    }
});

// Error handling
process.on('unhandledRejection', error => {
    console.error('Unhandled promise rejection:', error);
});

// Login
if (!process.env.DISCORD_TOKEN) {
    console.error('✗ DISCORD_TOKEN not found in .env file!');
    console.error('Please copy .env.example to .env and add your bot token.');
    process.exit(1);
}

client.login(process.env.DISCORD_TOKEN);
