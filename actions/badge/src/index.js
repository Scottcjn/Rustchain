const core = require('@actions/core');
const https = require('https');
const fs = require('fs');

// Disable SSL certificate validation (for self-signed certs)
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

async function fetchWalletData(wallet, nodeUrl) {
  return new Promise((resolve, reject) => {
    const url = `${nodeUrl}/wallet/balance?miner_id=${encodeURIComponent(wallet)}`;
    
    https.get(url, (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
        } catch (e) {
          reject(new Error(`Failed to parse response: ${e.message}`));
        }
      });
    }).on('error', (err) => {
      reject(new Error(`Request failed: ${err.message}`));
    });
  });
}

async function fetchEpochData(nodeUrl) {
  return new Promise((resolve, reject) => {
    https.get(`${nodeUrl}/epoch`, (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
        } catch (e) {
          reject(new Error(`Failed to parse epoch: ${e.message}`));
        }
      });
    }).on('error', (err) => {
      reject(err);
    });
  });
}

async function run() {
  try {
    // Get inputs
    const wallet = core.getInput('wallet', { required: true });
    const nodeUrl = core.getInput('node-url') || 'https://50.28.86.131';
    const badgeStyle = core.getInput('badge-style') || 'flat';
    
    core.info(`Fetching data for wallet: ${wallet}`);
    
    // Fetch wallet and epoch data
    const [walletData, epochData] = await Promise.all([
      fetchWalletData(wallet, nodeUrl),
      fetchEpochData(nodeUrl).catch(() => ({ epoch: '?' }))
    ]);
    
    const balance = walletData.amount_rtc || 0;
    const epoch = epochData.epoch || '?';
    
    // Determine status and color
    let status = 'Active';
    let color = 'brightgreen';
    
    if (balance === 0) {
      status = 'New';
      color = 'yellow';
    } else if (balance > 100) {
      color = 'success';
    }
    
    // Generate shields.io badge JSON
    const badgeData = {
      schemaVersion: 1,
      label: '⛏️ RustChain',
      message: `${balance.toFixed(1)} RTC | Epoch ${epoch} | ${status}`,
      color: color,
      style: badgeStyle
    };
    
    // Save badge JSON for external use
    fs.writeFileSync('rustchain-badge.json', JSON.stringify(badgeData, null, 2));
    
    // Generate shields.io URL
    const encodedMessage = encodeURIComponent(badgeData.message);
    const badgeUrl = `https://img.shields.io/badge/${encodeURIComponent(badgeData.label)}-${encodedMessage}-${color}?style=${badgeStyle}`;
    
    // Set outputs
    core.setOutput('badge-url', badgeUrl);
    core.setOutput('balance', balance.toString());
    core.setOutput('epoch', epoch.toString());
    
    core.info(`✅ Badge generated successfully`);
    core.info(`🔗 Badge URL: ${badgeUrl}`);
    core.info(`💰 Balance: ${balance} RTC`);
    core.info(`⏱️ Epoch: ${epoch}`);
    
    // Set summary
    await core.summary
      .addHeading('RustChain Mining Status')
      .addImage(badgeUrl, 'RustChain Badge')
      .addTable([
        [{data: 'Wallet', header: true}, {data: wallet}],
        [{data: 'Balance', header: true}, {data: `${balance} RTC`}],
        [{data: 'Epoch', header: true}, {data: epoch}],
        [{data: 'Status', header: true}, {data: status}]
      ])
      .write();
      
  } catch (error) {
    core.setFailed(`Action failed: ${error.message}`);
  }
}

run();