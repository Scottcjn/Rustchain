const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('health')
        .setDescription('Check RustChain network and node health status'),
    
    async execute(interaction, api) {
        await interaction.deferReply();
        
        try {
            // Query multiple health endpoints
            const [networkStatus, nodeStats, peerInfo] = await Promise.all([
                api.get('/health/network').catch(() => ({ data: null })),
                api.get('/health/stats').catch(() => ({ data: null })),
                api.get('/health/peers').catch(() => ({ data: null }))
            ]);
            
            // Determine overall status
            const networkHealthy = networkStatus.data?.healthy ?? false;
            const statusEmoji = networkHealthy ? '🟢' : '🔴';
            const statusText = networkHealthy ? 'Healthy' : 'Degraded';
            
            // Build status fields
            const fields = [];
            
            // Network status
            if (networkStatus.data) {
                fields.push(
                    { name: 'Network Status', value: `${statusEmoji} **${statusText}**`, inline: true },
                    { name: 'Chain Height', value: `**${networkStatus.data.block_height || 0}**`, inline: true },
                    { name: 'Active Nodes', value: `**${networkStatus.data.active_nodes || 0}**`, inline: true }
                );
            }
            
            // Node statistics
            if (nodeStats.data) {
                fields.push(
                    { name: 'TPS', value: `**${nodeStats.data.tps || 0}**`, inline: true },
                    { name: 'Avg Block Time', value: `**${nodeStats.data.avg_block_time || 0}s**`, inline: true },
                    { name: 'Pending Txns', value: `**${nodeStats.data.pending_transactions || 0}**`, inline: true }
                );
            }
            
            // Peer information
            if (peerInfo.data) {
                fields.push(
                    { name: 'Connected Peers', value: `**${peerInfo.data.connected_peers || 0}**`, inline: true },
                    { name: 'Sync Status', value: peerInfo.data.is_syncing ? '🔄 Syncing' : '✅ Synced', inline: true }
                );
            }
            
            // Create embed
            const embed = new EmbedBuilder()
                .setColor(networkHealthy ? 0x00FF00 : 0xFF0000)
                .setTitle('🏥 RustChain Health Status')
                .addFields(fields)
                .setFooter({ text: 'Real-time Network Health' })
                .setTimestamp();
            
            // Add uptime if available
            if (networkStatus.data?.uptime) {
                embed.addFields({
                    name: 'Uptime',
                    value: `**${formatUptime(networkStatus.data.uptime)}**`,
                    inline: false
                });
            }
            
            await interaction.editReply({ embeds: [embed] });
            
        } catch (error) {
            console.error('Health check error:', error.message);
            
            await interaction.editReply({
                content: `❌ Failed to fetch health data: ${error.message}\n\nThe API might be temporarily unavailable.`
            });
        }
    }
};

/**
 * Format uptime in human-readable format
 */
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    
    return parts.join(' ') || '< 1m';
}
