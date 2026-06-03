const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

const API_BASE = 'https://50.28.86.131';

module.exports = {
  data: new SlashCommandBuilder()
    .setName('miners')
    .setDescription('View top miners or specific miner info')
    .addIntegerOption(option =>
      option.setName('limit')
        .setDescription('Number of miners to display (1-20)')
        .setMinValue(1)
        .setMaxValue(20)
        .setValue(10)
    )
    .addStringOption(option =>
      option.setName('address')
        .setDescription('Specific miner address to lookup')
    ),
  
  async execute(interaction) {
    await interaction.deferReply();
    
    const limit = interaction.options.getInteger('limit') || 10;
    const address = interaction.options.getString('address');
    
    try {
      const response = await fetch(`${API_BASE}/api/miners`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const payload = await response.json();
      let miners = Array.isArray(payload)
        ? payload
        : Array.isArray(payload?.miners)
          ? payload.miners
          : [];
      
      // Filter by address if provided
      if (address) {
        miners = miners.filter(m => 
          getMinerId(m).toLowerCase().includes(address.toLowerCase())
        );
      }
      
      // Limit results
      miners = miners.slice(0, limit);
      
      if (miners.length === 0) {
        await interaction.editReply({
          content: '❌ No miners found matching your criteria.'
        });
        return;
      }
      
      // Create embed for each miner (or combined)
      if (miners.length === 1) {
        // Single miner detail
        const miner = miners[0];
        const embed = new EmbedBuilder()
          .setColor(0x0099FF)
          .setTitle('⛏️ Miner Details')
          .addFields(
            { name: 'Miner ID', value: `\`${getMinerId(miner)}\``, inline: false },
            { name: 'Hardware', value: `${miner.hardware_type || 'N/A'}`, inline: true },
            { name: 'Architecture', value: `${miner.device_arch || 'N/A'}`, inline: true },
            { name: 'Family', value: `${miner.device_family || 'N/A'}`, inline: true },
            { name: 'Antiquity Multiplier', value: `**${miner.antiquity_multiplier ?? 'N/A'}x**`, inline: true },
            { name: 'Entropy Score', value: `${miner.entropy_score ?? 'N/A'}`, inline: true },
            { name: 'Last Attest', value: `${formatTimestamp(miner.last_attest || miner.ts_ok)}`, inline: true }
          )
          .setFooter({ text: 'RustChain Proof-of-Antiquity' })
          .setTimestamp();
        
        await interaction.editReply({ embeds: [embed] });
      } else {
        // Multiple miners list
        const description = miners.map((m, i) => 
          `**${i + 1}.** ${getMinerId(m)}\n   Hardware: ${m.hardware_type || 'N/A'} | Multiplier: **${m.antiquity_multiplier ?? 'N/A'}x**`
        ).join('\n\n');
        
        const embed = new EmbedBuilder()
          .setColor(0x0099FF)
          .setTitle('⛏️ Top RustChain Miners')
          .setDescription(description)
          .setFooter({ text: `Showing ${miners.length} miners` })
          .setTimestamp();
        
        await interaction.editReply({ embeds: [embed] });
      }
      
    } catch (error) {
      console.error('Miners command error:', error);
      await interaction.editReply({
        content: `❌ Failed to fetch miners: ${error.message}`
      });
    }
  }
};

function formatTimestamp(unixTime) {
  if (!unixTime) return 'Never';
  const date = new Date(unixTime * 1000);
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function getMinerId(miner) {
  return String(miner?.miner || miner?.miner_id || 'unknown');
}
