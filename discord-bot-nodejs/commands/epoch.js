const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('epoch')
        .setDescription('View current RustChain epoch information')
        .addIntegerOption(option =>
            option.setName('epoch')
                .setDescription('Specific epoch number to query (optional)')
                .setRequired(false)
        ),
    
    async execute(interaction, api) {
        await interaction.deferReply();
        
        const epochNum = interaction.options.getInteger('epoch');
        
        try {
            // Query current or specific epoch
            const endpoint = epochNum ? `/epoch/${epochNum}` : '/epoch/current';
            const response = await api.get(endpoint);
            const epoch = response.data;
            
            // Calculate progress
            const progress = epoch.progress || 0;
            const progressBar = createProgressBar(progress, 20);
            
            const embed = new EmbedBuilder()
                .setColor(0x00AE86)
                .setTitle('📊 RustChain Epoch Status')
                .addFields(
                    { name: 'Epoch Number', value: `**#${epoch.epoch_number || 'N/A'}**`, inline: true },
                    { name: 'Status', value: epoch.is_active ? '🟢 Active' : '⏸️ Inactive', inline: true },
                    { name: 'Progress', value: `${progress.toFixed(1)}%`, inline: true }
                )
                .addFields(
                    { name: 'Progress Bar', value: progressBar, inline: false },
                    { name: 'Start Time', value: epoch.start_time ? `<t:${Math.floor(new Date(epoch.start_time).getTime() / 1000)}:R>` : 'N/A', inline: true },
                    { name: 'End Time', value: epoch.end_time ? `<t:${Math.floor(new Date(epoch.end_time).getTime() / 1000)}:R>` : 'N/A', inline: true }
                )
                .addFields(
                    { name: 'Total Validators', value: `**${epoch.validators || 0}**`, inline: true },
                    { name: 'Blocks Produced', value: `**${epoch.blocks_produced || 0}**`, inline: true },
                    { name: 'Rewards Distributed', value: `**${epoch.rewards_distributed || 0} RTC**`, inline: true }
                )
                .setFooter({ text: 'RustChain Epoch System' })
                .setTimestamp();
            
            await interaction.editReply({ embeds: [embed] });
            
        } catch (error) {
            console.error('Epoch query error:', error.response?.data || error.message);
            
            await interaction.editReply({
                content: `❌ Failed to fetch epoch data: ${error.response?.status === 404 ? 'Epoch not found' : error.message}`
            });
        }
    }
};

/**
 * Create a visual progress bar
 */
function createProgressBar(progress, length = 20) {
    const filled = Math.round((progress / 100) * length);
    const empty = length - filled;
    return `\`${'█'.repeat(filled)}░'.repeat(empty)}\` ${progress.toFixed(1)}%`;
}
