const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const nacl = require('tweetnacl');
const naclUtil = require('tweetnacl-util');
const { buildSignedTransfer, isValidChainId } = require('../signing');

const API_BASE = 'https://50.28.86.131';

// Signed transfers bind chain_id (cross-network replay protection). Use
// RUSTCHAIN_CHAIN_ID if set (validated), otherwise ask the node we are sending
// to; never guess.
let cachedChainId = null;
async function getChainId({ refresh = false } = {}) {
  const override = (process.env.RUSTCHAIN_CHAIN_ID || '').trim();
  if (override) {
    if (!isValidChainId(override)) throw new Error('RUSTCHAIN_CHAIN_ID is not a valid chain_id');
    return override;
  }
  if (cachedChainId && !refresh) return cachedChainId;
  cachedChainId = null;
  const resp = await fetch(`${API_BASE}/network/info`);
  if (!resp.ok) throw new Error(`network info HTTP ${resp.status}`);
  const info = await resp.json();
  if (!isValidChainId(info && info.chain_id)) throw new Error('node reported no usable chain_id');
  cachedChainId = info.chain_id;
  return cachedChainId;
}

// Sign + POST. If the node says our (cached) chain_id is not its network, refetch
// the chain_id once and re-sign with a fresh nonce; an explicit override is not retried.
async function sendChainBoundTransfer({ secretKeyBytes, toAddress, amountRtc, memo }) {
  let refresh = false;
  for (let attempt = 0; attempt < 2; attempt++) {
    const chainId = await getChainId({ refresh });
    const { body } = buildSignedTransfer(nacl, {
      secretKey: secretKeyBytes,
      toAddress,
      amountRtc,
      memo,
      nonce: Date.now() + attempt,
      chainId,
    });
    const response = await fetch(`${API_BASE}/wallet/transfer/signed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    const mismatch = response.status === 400 && /chain_id does not match/.test(String(data.error || ''));
    if (mismatch && attempt === 0 && !(process.env.RUSTCHAIN_CHAIN_ID || '').trim()) {
      refresh = true;
      continue;
    }
    if (!response.ok) throw new Error(data.error || `HTTP error! status: ${response.status}`);
    return data;
  }
  throw new Error('chain_id does not match active network');
}

module.exports = {
  _internal: { getChainId, sendChainBoundTransfer },
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
      // Build, sign (canonical, chain-bound) and send the transfer
      const result = await sendChainBoundTransfer({
        secretKeyBytes: naclUtil.decodeBase64(secretKey),
        toAddress: recipient,
        amountRtc: amount,
        memo: message,
      });

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
