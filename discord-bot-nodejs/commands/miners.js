const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('miners')
        .setDescription('View RustChain miner information and statistics')
        .addStringOption(option =>
            option.setName('address')
                .setDescription('Specific miner address to query')
                .setRequired(false)
        )
        .addIntegerOption(option =>
            option.setName('limit')
                .setDescription('Number of top miners to show (default: 10)')
                .setRequired(false)
        ),
    
    async execute(interaction, api) {
        await interaction.deferReply();
        
        const address = interaction.options.getString('address');
        const limit = interaction.options.getInteger('limit') || 10;
        
        try {
            let response;
            let embed;
            
            if (address) {
                // Query specific miner
                response = await api.get(`/miners/${address}`);
                const miner = response.data;
                
                embed = new EmbedBuilder()
                    .setColor(0x00AE86)
                    .setTitle('⛏️ Miner Information')
                    .addFields(
                        { name: 'Address', value: `\`${address.slice(0, 8)}...${address.slice(-8)}\``, inline: false },
                        { name: 'Hash Rate', value: `**${miner.hash_rate || 0} H/s**`, inline: true },
                        { name: 'Status', value: miner.is_online ? '🟢 Online' : '🔴 Offline', inline: true },
                        { name: 'Blocks Mined', value: `**${miner.blocks_mined || 0}**`, inline: true },
                        { name: 'Total Rewards', value: `**${miner.total_rewards || 0} RTC**`, inline: true },
                        { name: 'Last Share', value: miner.last_share ? `<t:${Math.floor(new Date(miner.last_share).getTime() / 1000)}:R>` : 'Never', inline: true }
                    )
                    .setFooter({ text: 'RustChain Mining Network' })
                    .setTimestamp();
                    
            } else {
                // Query top miners
                response = await api.get('/miners', { params: { limit } });
                const miners = response.data;
                
                const minerList = miners.slice(0, limit).map((miner, index) => {
                    return `**#${index + 1}** \`${miner.address.slice(0, 6)}...${miner.address.slice(-6)}\` - ${miner.hash_rate || 0} H/s`;
                }).join('\n');
                
                embed = new EmbedBuilder()
                    .setColor(0x00AE86)
                    .setTitle('⛏️ Top RustChain Miners')
                    .setDescription(minerList || 'No miners found')
                    .addFields(
                        { name: 'Total Miners', value: `**${miners.length}**`, inline: true },
                        { name: 'Network Hash Rate', value: `**${response.data.network_hash_rate || 'N/A'}**`, inline: true }
                    )
                    .setFooter({ text: 'RustChain Mining Network' })
                    .setTimestamp();
            }
            
            await interaction.editReply({ embeds: [embed] });
            
        } catch (error) {
            console.error('Miners query error:', error.response?.data || error.message);
            
            await interaction.editReply({
                content: `❌ Failed to fetch miner data: ${error.message}`
            });
        }
    }
};
