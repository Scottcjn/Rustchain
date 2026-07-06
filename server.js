const express = require('express');
const fs = require('fs').promises;
const path = require('path');
require('dotenv').config();

const app = express();
app.use(express.json());
app.use(express.static('.'));

const CLAIMS_FILE = path.join(__dirname, 'claims.json');
const CLAIM_LIMIT = 100;

// Helper to read and write claims
async function getClaims() {
    try {
        const data = await fs.readFile(CLAIMS_FILE, 'utf-8');
        return JSON.parse(data);
    } catch (err) {
        return [];
    }
}

async function saveClaims(claims) {
    await fs.writeFile(CLAIMS_FILE, JSON.stringify(claims, null, 2));
}

// Verify star via GitHub API
async function verifyStar(username, repoOwner, repoName, token) {
    const url = `https://api.github.com/repos/${repoOwner}/${repoName}/stargazers`;
    const response = await fetch(url, {
        headers: {
            'Authorization': `token ${token}`,
            'Accept': 'application/vnd.github.v3.star+json'
        }
    });
    if (!response.ok) throw new Error('GitHub API error: ' + response.status);
    const stargazers = await response.json();
    return stargazers.some(s => s.user?.login === username);
}

// Endpoint to submit claim
app.post('/api/claim', async (req, res) => {
    try {
        const { postLink, reviewLink, reason, wallet, username } = req.body;

        // Basic validation
        if (!postLink || !reviewLink || !reason || !username) {
            return res.status(400).json({ error: 'Missing required fields.' });
        }
        if (reason.length < 10) {
            return res.status(400).json({ error: 'Reason must be at least 10 characters.' });
        }

        // Check if already claimed (by username)
        let claims = await getClaims();
        if (claims.some(c => c.username === username)) {
            return res.status(409).json({ error: 'This account has already claimed the bounty.' });
        }

        // Check pool availability
        if (claims.length >= CLAIM_LIMIT) {
            return res.status(403).json({ error: 'Bounty pool is exhausted.' });
        }

        // Verify star (requires GITHUB_TOKEN env var)
        const token = process.env.GITHUB_TOKEN;
        if (!token) {
            return res.status(500).json({ error: 'Server not configured for GitHub verification.' });
        }
        const repoOwner = 'Scottcjn';
        const repoName = 'Rustchain';
        try {
            const hasStarred = await verifyStar(username, repoOwner, repoName, token);
            if (!hasStarred) {
                return res.status(400).json({ error: 'You must star the repository first.' });
            }
        } catch (err) {
            return res.status(500).json({ error: 'Failed to verify star: ' + err.message });
        }

        // Add claim
        const newClaim = {
            username,
            postLink,
            reviewLink,
            reason,
            wallet: wallet || 'pending',
            timestamp: new Date().toISOString(),
            status: 'pending'
        };
        claims.push(newClaim);
        await saveClaims(claims);

        // In production, trigger payout via smart contract or manual process
        res.json({ message: 'Claim submitted successfully! You will receive 3 RTC after review.', claimId: claims.length });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Internal server error.' });
    }
});

// Admin endpoint to list claims (basic auth not added for brevity)
app.get('/api/claims', async (req, res) => {
    const claims = await getClaims();
    res.json(claims);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Bounty server running on port ${PORT}`);
});
