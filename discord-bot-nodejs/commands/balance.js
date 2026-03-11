const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('balance')
        .setDescription('Check your RustChain (RTC) balance')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('Check another user\'s balance (optional)')
                .setRequired(false)
        )
        .addStringOption(option =>
            option.setName('address')
                .setDescription('Check balance by wallet address')
                .setRequired(false)
        ),
    
    async execute(interaction, api) {
        await interaction.deferReply();
        
        const targetUser = interaction.options.getUser('user');
        const address = interaction.options.getString('address');
        
        try {
            // Determine which address to query
            let queryAddress = address;
            
            if (!queryAddress && targetUser) {
                // TODO: Implement user-to-address mapping (database)
                return interaction.editReply({
                    content: '❌ User address mapping not implemented yet. Please use wallet address directly.'
                });
            }
            
            if (!queryAddress) {
                // TODO: Get address from user's Discord account
                return interaction.editReply({
                    content: '❌ Please provide a wallet address or link your account first.\nUsage: `/balance address:your_wallet_address`'
                });
            }
            
            // Query RustChain API
            const response = await api.get(`/balance/${queryAddress}`);
            const balance = response.data;
            
            // Create embed
            const embed = new EmbedBuilder()
                .setColor(0x00AE86) // RustChain green
                .setTitle('💰 RustChain Balance')
                .addFields(
                    { name: 'Address', value: `\`${queryAddress.slice(0, 8)}...${queryAddress.slice(-8)}\``, inline: true },
                    { name: 'Balance', value: `**${balance.balance || 0} RTC**`, inline: true },
                    { name: 'USD Value', value: `$${balance.usd_value || '0.00'}`, inline: true }
                )
                .addFields(
                    { name: 'Last Updated', value: `<t:${Math.floor(Date.now() / 1000)}:R>`, inline: false }
                )
                .setFooter({ text: 'RustChain Network' })
                .setTimestamp();
            
            await interaction.editReply({ embeds: [embed] });
            
        } catch (error) {
            console.error('Balance query error:', error.response?.data || error.message);
            
            await interaction.editReply({
                content: `❌ Failed to fetch balance: ${error.response?.status === 404 ? 'Address not found' : error.message}`
            });
        }
    }
};
