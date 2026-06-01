import { RustChainClient } from "../src/index.js";

const client = new RustChainClient({
  baseUrl: process.env.RUSTCHAIN_NODE_URL || "https://rustchain.org"
});

const health = await client.health();
const epoch = await client.epoch();
const miners = await client.miners({ limit: 10 });

console.log(JSON.stringify({
  health,
  epoch,
  minerCount: miners.length
}, null, 2));
