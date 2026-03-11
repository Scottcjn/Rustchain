const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

const API_BASE = 'https://50.28.86.131';

module.exports = {
  data: new SlashCommandBuilder()
    .setName('health')
    .setDescription('Check RustChain node health status'),
  
  async execute(interaction) {
    await interaction.deferReply();
    
    try {
      const response = await fetch(`${API_BASE}/health`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      const embed = new EmbedBuilder()
        .setColor(data.ok ? 0x00FF00 : 0xFF0000)
        .setTitle('🏥 RustChain Node Health')
        .addFields(
          { name: 'Status', value: data.ok ? '✅ Online' : '❌ Offline', inline: true },
          { name: 'Version', value: `\`${data.version}\``, inline: true },
          { name: 'Database', value: data.db_rw ? '✅ Read/Write' : '❌ Read-Only', inline: true },
          { name: 'Uptime', value: `${formatUptime(data.uptime_s)}`, inline: true },
          { name: 'Backup Age', value: `${data.backup_age_hours.toFixed(2)} hours`, inline: true },
          { name: 'Tip Age', value: `${data.tip_age_slots} slots`, inline: true }
        )
        .setFooter({ text: 'RustChain Network' })
        .setTimestamp();
      
      await interaction.editReply({ embeds: [embed] });
      
    } catch (error) {
      console.error('Health command error:', error);
      await interaction.editReply({
        content: `❌ Failed to fetch health status: ${error.message}`
      });
    }
  }
};

function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  
  if (days > 0) return `${days}d ${hours}h ${mins}m`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}
