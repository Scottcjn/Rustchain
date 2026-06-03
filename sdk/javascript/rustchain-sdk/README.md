# RustChain JavaScript SDK

Lightweight JavaScript SDK for the RustChain node API. It works in Node.js 18+ and modern browsers that provide `fetch`.

## Install

This package is currently shipped from the RustChain repository:

```bash
cd sdk/javascript/rustchain-sdk
npm test
```

## Usage

```js
import { RustChainClient } from "./src/index.js";

const client = new RustChainClient({
  baseUrl: "https://rustchain.org"
});

const health = await client.health();
const epoch = await client.epoch();
const miners = await client.miners({ limit: 10 });

console.log({ health, epoch, miners });
```

## API

### `new RustChainClient(options)`

Options:

- `baseUrl`: RustChain node URL. Defaults to `https://rustchain.org`.
- `timeoutMs`: request timeout in milliseconds. Defaults to `30000`.
- `fetch`: optional custom fetch implementation for tests or older runtimes.

### Public methods

- `health()` -> `GET /health`
- `epoch()` -> `GET /epoch`
- `miners({ limit, offset, hardwareType })` -> `GET /api/miners`
- `balance(minerId)` -> `GET /wallet/balance?miner_id=...`
- `transfer({ from, to, amount, signature, fee })` -> `POST /transfer`
- `attestChallenge(payload)` -> `POST /attest/challenge`
- `submitAttestation(payload)` -> `POST /attest/submit`
- `transferHistory(wallet, { limit })` -> `GET /wallet/history`

## Example

```bash
RUSTCHAIN_NODE_URL=https://50.28.86.131 node examples/health.js
```

## Validation

```bash
npm test
```

The test suite uses Node's built-in `node:test` runner and mocked `fetch`, so it does not require network access or dependency installation.
