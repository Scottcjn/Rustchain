const core = require('@actions/core');
const github = require('@actions/github');

async function run() {
    try {
        const nodeUrl = core.getInput('node-url');
        const amount = core.getInput('amount');
        const walletFrom = core.getInput('wallet-from');
        const adminKey = core.getInput('admin-key');
        const dryRun = core.getInput('dry-run') === 'true';
        const walletField = core.getInput('wallet-field');

        const context = github.context;
        if (context.eventName !== 'pull_request' || context.payload.pull_request.merged !== true) {
            core.info('PR not merged or event not pull_request. Skipping reward.');
            return;
        }

        const prBody = context.payload.pull_request.body || '';
        let walletTo = '';

        // 1. Search in PR body for "Wallet: <name>"
        const walletRegex = new RegExp(`${walletField}:\s*(\S+)`, 'i');
        const match = prBody.match(walletRegex);
        if (match) {
            walletTo = match[1].trim();
            core.info(`Found wallet in PR body: ${walletTo}`);
        }

        // 2. Fallback to GitHub username
        if (!walletTo) {
            walletTo = context.payload.pull_request.user.login;
            core.info(`No wallet found in body. Falling back to GitHub username: ${walletTo}`);
        }

        core.info(`Attempting to reward ${amount} RTC to ${walletTo} from ${walletFrom}`);

        if (dryRun) {
            core.info('[DRY RUN] Simulating transfer...');
            core.setOutput('result', 'dry-run');
            core.setOutput('wallet-to', walletTo);
            core.setOutput('amount', amount);
            
            const comment = `🎉 **Dry Run Reward**: ${amount} RTC would be awarded to ${walletTo}.\n\n_This was a simulation._`;
            await createPRComment(comment);
            return;
        }

        // Actual API Call to RustChain
        const response = await fetch(`${nodeUrl}/wallet/transfer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Key': adminKey
            },
            body: JSON.stringify({
                from_miner: walletFrom,
                to_miner: walletTo,
                amount_rtc: parseFloat(amount),
                memo: `Reward for merged PR #${context.payload.pull_request.number}`
            })
        });

        const result = await response.json();

        if (response.ok && result.ok) {
            core.info(`Successfully awarded ${amount} RTC to ${walletTo}`);
            core.setOutput('result', 'success');
            core.setOutput('wallet-to', walletTo);
            core.setOutput('tx_id', result.tx_id || 'N/A');

            const comment = `🎉 **RTC Reward Sent**: ${amount} RTC awarded to ${walletTo}!\n\nTransaction ID: ${result.tx_id || 'N/A'}\nThank you for your contribution!`;
            await createPRComment(comment);
        } else {
            const errorMsg = result.error || 'Unknown API error';
            core.setFailed(`Failed to send RTC reward: ${errorMsg}`);
            
            const comment = `❌ **RTC Reward Failed**: ${errorMsg}. Please contact the maintainers.`;
            await createPRComment(comment);
        }

    } catch (error) {
        core.setFailed(`Action failed with error: ${error.message}`);
    }
}

async function createPRComment(text) {
    const { owner, repo } = github.context.repo;
    const prNumber = github.context.payload.pull_request.number;
    
    try {
        await github.rest.issues.createComment({
            owner,
            repo,
            issue_number: prNumber,
            body: text
        });
        core.info('Comment posted successfully.');
    } catch (e) {
        core.error(`Failed to post comment: ${e.message}`);
    }
}

run();
