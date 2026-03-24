# RustChain Python SDK

Python SDK for RustChain nodes. Install: pip install rustchain

## Quickstart

    async with RustChainClient() as client:
        health = await client.health()
        epoch = await client.epoch()
        balance = await client.balance('wallet-id')
        miners = await client.miners(limit=20)

## CLI

    rustchain balance <wallet>
    rustchain epoch
    rustchain miners
    rustchain health

## Wallet
C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
