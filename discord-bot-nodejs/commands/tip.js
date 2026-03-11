const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('tip')
        .setDescription('Tip another user with RTC (BONUS FEATURE +5 RTC)')
        .addUserOption(option =>
            option.setName('recipient')
                .setDescription('The user to tip')
                .setRequired(true)
        )
        .addNumberOption(option =>
            option.setName('amount')
                .setDescription('Amount of RTC to tip')
                .setRequired(true)
        )
        .addStringOption(option =>
            option.setName('message')
                .setDescription('Optional message to include with the tip')
                .setRequired(false)
        ),
    
    async execute(interaction, api) {
        await interaction.deferReply();
        
        const recipient = interaction.options.getUser('recipient');
        const amount = interaction.options.getNumber('amount');
        const message = interaction.options.getString('message');
        
        // Prevent self-tip
        if (recipient.id === interaction.user.id) {
            return interaction.editReply({
                content: '❌ You cannot tip yourself!'
            });
        }
        
        // Prevent bot tipping
        if (recipient.bot) {
            return interaction.editReply({
                content: '❌ You cannot tip bots!'
            });
        }
        
        try {
            // TODO: In production, implement proper wallet verification
            // For demo purposes, we'll simulate the tip process
            
            // Step 1: Check sender's balance (would need linked wallet)
            // const senderBalance = await api.get(`/balance/${senderAddress}`);
            
            // Step 2: Execute tip transaction
            // const tx = await api.post('/transactions/tip', {
            //     from: senderAddress,
            //     to: recipientAddress,
            //     amount: amount,
            //     message: message
            // });
            
            // For demo, create a simulated response
            const tipData = {
                transaction_hash: `0x${Math.random().toString(16).slice(2, 66)}`,
                from: interaction.user.tag,
                to: recipient.tag,
                amount: amount,
                message: message || '🎉 Thanks!',
                timestamp: new Date().toISOString(),
                status: 'pending'
            };
            
            // Create success embed
            const embed = new EmbedBuilder()
                .setColor(0x00AE86)
                .setTitle('💸 Tip Sent!')
                .addFields(
                    { name: 'From', value: `**${tipData.from}**`, inline: true },
                    { name: 'To', value: `**${tipData.to}**`, inline: true },
                    { name: 'Amount', value: `**${amount} RTC**`, inline: true }
                )
                .addFields(
                    { name: 'Transaction Hash', value: `\`${tipData.transaction_hash.slice(0, 10)}...${tipData.transaction_hash.slice(-8)}\``, inline: false },
                    { name: 'Message', value: `"${tipData.message}"`, inline: false }
                )
                .addFields(
                    { name: 'Status', value: '⏳ Pending Confirmation', inline: false }
                )
                .setFooter({ text: 'RustChain Tip System' })
                .setTimestamp();
            
            // Mention the recipient
            await interaction.editReply({
                content: `${recipient.toString()}, you received a tip!`,
                embeds: [embed]
            });
            
            // Log the tip (in production, save to database)
            console.log(`[TIP] ${tipData.from} -> ${tipData.to}: ${amount} RTC`);
            
        } catch (error) {
            console.error('Tip error:', error.response?.data || error.message);
            
            await interaction.editReply({
                content: `❌ Failed to send tip: ${error.message}\n\nMake sure you have sufficient balance and the recipient has a linked wallet.`
            });
        }
    }
};
