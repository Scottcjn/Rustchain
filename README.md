# RustChain Bounty Claim System

Simple web server for processing bounty claims for the "Share Your Star" campaign.

## Setup

1. Clone and install dependencies: `npm install`
2. Copy `.env.example` to `.env` and set your GitHub Personal Access Token (with `public_repo` scope).
3. Run `npm start`
4. Open `http://localhost:3000`

## Endpoints

- `POST /api/claim` - Submit a bounty claim
- `GET /api/claims` - View all claims (admin)

## Claim Process

1. User stars the repo on GitHub.
2. User posts about RustChain on any platform.
3. User fills out the form with:
   - Link to post
   - Link to a specific file/feature they reviewed
   - A specific non-generic reason for liking it
   - (Optional) RTC wallet address
   - GitHub username (for star verification)
   - FTC disclosure checkbox
4. Server verifies the star via GitHub API.
5. Claim is recorded; payout happens manually or via smart contract.

## Rules Enforced

- One claim per GitHub account.
- Pool limit of 100 claims (300 RTC).
- Star must be active.
- Reason must be specific (≥10 chars).
