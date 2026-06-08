import test from "node:test";
import assert from "node:assert/strict";
import {
  RustChainApiError,
  RustChainClient,
  RustChainValidationError,
  createClient
} from "../src/index.js";

function mockFetch(handler) {
  return async (url, init) => {
    const result = await handler(url, init);
    return {
      ok: result.status >= 200 && result.status < 300,
      status: result.status,
      text: async () => result.body ?? "{}"
    };
  };
}

test("creates a client with defaults", () => {
  const client = createClient({ fetch: mockFetch(() => ({ status: 200 })) });
  assert.equal(client.baseUrl, "https://rustchain.org");
});

test("normalizes base URL", () => {
  const client = new RustChainClient({
    baseUrl: "https://example.test///",
    fetch: mockFetch(() => ({ status: 200 }))
  });
  assert.equal(client.baseUrl, "https://example.test");
});

test("fetches health endpoint", async () => {
  const client = new RustChainClient({
    baseUrl: "https://node.test",
    fetch: mockFetch((url, init) => {
      assert.equal(url, "https://node.test/health");
      assert.equal(init.method, "GET");
      return { status: 200, body: JSON.stringify({ ok: true, version: "2.2.1-rip200" }) };
    })
  });

  assert.deepEqual(await client.health(), { ok: true, version: "2.2.1-rip200" });
});

test("normalizes miners array responses", async () => {
  const client = new RustChainClient({
    fetch: mockFetch((url) => {
      assert.equal(url, "https://rustchain.org/api/miners?limit=5&offset=2&hardware_type=PowerPC");
      return { status: 200, body: JSON.stringify({ miners: [{ miner: "alice" }] }) };
    })
  });

  assert.deepEqual(await client.miners({ limit: 5, offset: 2, hardwareType: "PowerPC" }), [{ miner: "alice" }]);
});

test("validates balance miner id", async () => {
  const client = new RustChainClient({ fetch: mockFetch(() => ({ status: 200 })) });
  await assert.rejects(() => client.balance(""), RustChainValidationError);
});

test("posts signed transfer payload", async () => {
  const fromAddress = `RTC${"a".repeat(40)}`;
  const toAddress = `RTC${"b".repeat(40)}`;

  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      assert.equal(url, "https://rustchain.org/wallet/transfer/signed");
      assert.equal(init.method, "POST");
      assert.deepEqual(JSON.parse(init.body), {
        from_address: fromAddress,
        to_address: toAddress,
        amount_rtc: 1.25,
        fee_rtc: 0,
        nonce: 12345,
        signature: "22".repeat(64),
        public_key: "11".repeat(32),
        memo: "sdk transfer",
        chain_id: "rustchain-mainnet-v2"
      });
      return { status: 200, body: JSON.stringify({ success: true }) };
    })
  });

  assert.deepEqual(
    await client.transfer({
      from: fromAddress,
      to: toAddress,
      amount: 1.25,
      nonce: 12345,
      signature: "22".repeat(64),
      publicKey: "11".repeat(32),
      memo: "sdk transfer",
      chainId: "rustchain-mainnet-v2"
    }),
    { success: true }
  );
});

test("rejects signed transfer calls missing signature material", async () => {
  const client = new RustChainClient({ fetch: mockFetch(() => ({ status: 200 })) });

  await assert.rejects(
    () =>
      client.transfer({
        from: `RTC${"a".repeat(40)}`,
        to: `RTC${"b".repeat(40)}`,
        amount: 1.25,
        nonce: 12345,
        signature: "22".repeat(64)
      }),
    RustChainValidationError
  );
});

test("throws API errors with status and endpoint", async () => {
  const client = new RustChainClient({
    fetch: mockFetch(() => ({ status: 500, body: JSON.stringify({ error: "boom" }) }))
  });

  await assert.rejects(
    () => client.epoch(),
    (error) => error instanceof RustChainApiError && error.status === 500 && error.endpoint === "/epoch"
  );
});
