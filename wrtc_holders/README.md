# wRTC Holder Snapshot Tool

A command-line tool to query the Solana blockchain and list all wallets holding wRTC tokens.

## Installation

```bash
# Clone or download this repository
cd wrtc-holder-list

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the tool
python3 wrtc_holders.py

# Run test version with mock data
python3 test_wrtc_holders.py
```

## Output Example

```
wRTC Token Holder Snapshot
======================================================================

Mint: 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
Total Supply: 8,300,000 wRTC

Fetching token supply...
Actual Supply: 8,300,000 wRTC

Fetching token holders...
Holders found: 15

======================================================================
Rank  Wallet                                          Balance      % Supply Label     
-------------------------------------------------------------------------------------
1     3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW     8,296,082  99.95% [Reserve] 
2     8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb         4,000   0.05% [Raydium LP]
3     5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1         1,000   0.01% [Team]    
...

Summary
======================================================================
Total Holders: 15
Top Holder: 8,296,082 wRTC (99.95%)
Gini Coefficient: 0.850 (0 = equal, 1 = concentrated)
Whales (>1% supply): 1
  - 3n7RJanhRghRzW2P...: 8,296,082 wRTC ([Reserve])

Labels:
  [Reserve]   = Project reserve wallet
  [Raydium LP] = Liquidity pool on Raydium
  [Team]      = Team/Dev wallet
```

## Token Details

- **Mint:** `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- **Decimals:** 6
- **Supply:** 8,300,000 wRTC (fixed, mint authority revoked)

## Known Wallet Labels

The tool automatically labels known wallet addresses:

| Address | Label |
|---------|-------|
| `3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW` | [Reserve] |
| `8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb` | [Raydium LP] |
| `5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1` | [Team] |

## How It Works

1. **RPC Query:** Uses Solana RPC `getTokenLargestAccounts` to fetch holder data
2. **Supply Check:** Verifies total supply with `getTokenSupply`
3. **Formatting:** Converts raw balances to human-readable format
4. **Labeling:** Adds labels to known wallets (reserve, LP, team)
5. **Analysis:** Calculates concentration metrics (Gini, whales)

## RPC Endpoints

The tool tries multiple public RPC endpoints in order:
1. `https://api.mainnet-beta.solana.com` (official)
2. `https://solana-api.projectserum.com`
3. `https://rpc.ankr.com/solana`

You can specify a custom RPC endpoint by modifying the code or setting environment variables.

## Requirements

- Python 3.6+
- requests library

## Features

- ✅ Lists all wRTC holders with balances
- ✅ Shows percentage of total supply
- ✅ Labels known wallets (reserve, LP, team)
- ✅ Calculates concentration metrics (Gini coefficient)
- ✅ Identifies whale wallets (>1% of supply)
- ✅ Fast and easy to use
- ✅ No API key required for public endpoints

## License

MIT

## Related Links

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [wRTC on Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
- [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)
