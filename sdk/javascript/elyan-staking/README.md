# @elyan/staking

TypeScript staking SDK for RustChain — stake RTC, submit results, poll for
verdicts, and verify Ed25519-signed attestations.

```
npm install @elyan/staking
```

## Usage

```typescript
import { createStakingClient } from "@elyan/staking";

const client = createStakingClient({
  apiKey: "your-gate-api-key",
  gatePubkey: "base64-encoded-ed25519-public-key",
});

// 1. Stake RTC on a skill
const { taskId } = await client.stake({
  skill: "code-review",
  bondRtc: 10,
});

// 2. Submit your result
await client.submit({
  taskId,
  result: { passed: true, summary: "All checks OK" },
});

// 3. Poll for verdict
const { status, verdict } = await client.poll(taskId);

// 4. Verify the signed verdict
const { valid, signer } = await client.verify(verdict);
```

## API

### `stake(request)`

| Field     | Type     | Required | Description               |
|-----------|----------|----------|---------------------------|
| `skill`   | string   | ✅       | Skill/domain identifier   |
| `bondRtc` | number   | ✅       | Amount of RTC to bond     |
| `agentId` | string   | ❌       | Optional agent identifier |

### `submit(request)`

| Field    | Type   | Required | Description        |
|----------|--------|----------|--------------------|
| `taskId` | string | ✅       | From stake() call  |
| `result` | object | ✅       | Freeform result    |

### `poll(taskId)`

Returns the current task status and optional verdict/attestation.

### `verify(verdict, pubkey?)`

Verifies an Ed25519 verdict. If `gatePubkey` was set in the constructor
you can omit the second parameter.

## License

MIT
