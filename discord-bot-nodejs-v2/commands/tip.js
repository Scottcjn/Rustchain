const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const nacl = require('tweetnacl');
const naclUtil = require('tweetnacl-util');

const API_BASE = 'https://50.28.86.131';

module.exports = {
  data: new SlashCommandBuilder()
    .setName('tip')
    .setDescription('Tip another user with RTC (requires configured wallet)')
    .addStringOption(option =>
      option.setName('recipient')
        .setDescription('Recipient wallet address')
        .setRequired(true)
    )
    .addNumberOption(option =>
      option.setName('amount')
        .setDescription('Amount of RTC to send')
        .setRequired(true)
        .setMinValue(0.001)
    )
    .addStringOption(option =>
      option.setName('message')
        .setDescription('Optional message to include')
    ),
  
  async execute(interaction) {
    await interaction.deferReply({ ephemeral: true });
    
    const recipient = interaction.options.getString('recipient');
    const amount = interaction.options.getNumber('amount');
    const message = interaction.options.getString('message') || '';
    
    // Check if wallet is configured
    const secretKey = process.env.WALLET_SECRET_KEY;
    const publicKey = process.env.WALLET_PUBLIC_KEY;
    
    if (!secretKey || !publicKey) {
      const embed = new EmbedBuilder()
        .setColor(0xFF0000)
        .setTitle('❌ Wallet Not Configured')
        .setDescription('This bot requires a configured wallet to send tips.\n\n' +
          '**Setup Instructions:**\n' +
          '1. Generate Ed25519 keypair\n' +
          '2. Add `WALLET_SECRET_KEY` and `WALLET_PUBLIC_KEY` to `.env`\n' +
          '3. Restart the bot')
        .addFields(
          { name: 'Generate Keys', value: 'Use `tweetnacl` or RustChain SDK' }
        );
      
      await interaction.editReply({ embeds: [embed] });
      return;
    }
    
    try {
      // Create transfer payload
      const transferData = {
        from: publicKey,
        to: recipient,
        amount: amount,
        timestamp: Date.now()
      };
      
      // Sign the transfer
      const messageBytes = naclUtil.decodeUTF8(JSON.stringify(transferData));
      const secretKeyBytes = naclUtil.decodeBase64(secretKey);
      const signature = nacl.sign.detached(messageBytes, secretKeyBytes);
      const signatureHex = Buffer.from(signature).toString('hex');
      
      // Send signed transaction to API
      const response = await fetch(`${API_BASE}/wallet/transfer/signed`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...transferData,
          signature: signatureHex
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      const embed = new EmbedBuilder()
        .setColor(0x00FF00)
        .setTitle('✅ Tip Sent Successfully!')
        .addFields(
          { name: 'Recipient', value: `\`${recipient}\``, inline: true },
          { name: 'Amount', value: `**${amount} RTC**`, inline: true },
          { name: 'Transaction Hash', value: `\`${result.tx_hash}\``, inline: false },
          { name: 'Message', value: message || 'No message', inline: false }
        )
        .setFooter({ text: 'RustChain Wallet' })
        .setTimestamp();
      
      await interaction.editReply({ embeds: [embed] });
      
    } catch (error) {
      console.error('Tip command error:', error);
      await interaction.editReply({
        content: `❌ Failed to send tip: ${error.message}`
      });
    }
  }
};
