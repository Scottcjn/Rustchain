const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

const API_BASE = 'https://50.28.86.131';

module.exports = {
  data: new SlashCommandBuilder()
    .setName('balance')
    .setDescription('Check RTC balance for a miner wallet')
    .addStringOption(option =>
      option.setName('miner_id')
        .setDescription('Miner wallet address or ID')
        .setRequired(true)
    ),
  
  async execute(interaction) {
    await interaction.deferReply();
    
    const minerId = interaction.options.getString('miner_id');
    
    try {
      const response = await fetch(`${API_BASE}/wallet/balance?miner_id=${encodeURIComponent(minerId)}`);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      const embed = new EmbedBuilder()
        .setColor(0xFFD700)
        .setTitle('💰 RustChain Balance')
        .addFields(
          { name: 'Miner ID', value: `\`${data.miner_id}\``, inline: false },
          { name: 'Balance', value: `**${data.amount_rtc.toLocaleString()} RTC**`, inline: true },
          { name: 'Amount (i64)', value: `${data.amount_i64.toLocaleString()}`, inline: true }
        )
        .setFooter({ text: 'RustChain Wallet' })
        .setTimestamp();
      
      await interaction.editReply({ embeds: [embed] });
      
    } catch (error) {
      console.error('Balance command error:', error);
      await interaction.editReply({
        content: `❌ Failed to fetch balance: ${error.message}`
      });
    }
  }
};
