const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

const API_BASE = 'https://50.28.86.131';

module.exports = {
  data: new SlashCommandBuilder()
    .setName('epoch')
    .setDescription('Get current epoch information'),
  
  async execute(interaction) {
    await interaction.deferReply();
    
    try {
      const response = await fetch(`${API_BASE}/epoch`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      const embed = new EmbedBuilder()
        .setColor(0x0099FF)
        .setTitle('📅 RustChain Epoch Info')
        .addFields(
          { name: 'Epoch', value: `**#${data.epoch}**`, inline: true },
          { name: 'Slot', value: `${data.slot.toLocaleString()}`, inline: true },
          { name: 'Blocks/Epoch', value: `${data.blocks_per_epoch}`, inline: true },
          { name: 'Enrolled Miners', value: `${data.enrolled_miners}`, inline: true },
          { name: 'Epoch POT', value: `${data.epoch_pot}`, inline: true },
          { name: 'Total Supply', value: `${data.total_supply_rtc.toLocaleString()} RTC`, inline: true }
        )
        .setFooter({ text: 'RustChain Proof-of-Antiquity' })
        .setTimestamp();
      
      await interaction.editReply({ embeds: [embed] });
      
    } catch (error) {
      console.error('Epoch command error:', error);
      await interaction.editReply({
        content: `❌ Failed to fetch epoch info: ${error.message}`
      });
    }
  }
};
