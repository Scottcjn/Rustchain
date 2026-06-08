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

test("posts transfer payload", async () => {
  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      assert.equal(url, "https://rustchain.org/transfer");
      assert.equal(init.method, "POST");
      assert.deepEqual(JSON.parse(init.body), {
        from: "alice",
        to: "bob",
        amount: 1.25,
        fee: 0.01
      });
      return { status: 200, body: JSON.stringify({ success: true }) };
    })
  });

  assert.deepEqual(await client.transfer({ from: "alice", to: "bob", amount: 1.25 }), { success: true });
});

test("fetches transfer history with the live miner_id query", async () => {
  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      assert.equal(url, "https://rustchain.org/wallet/history?miner_id=alice&limit=5");
      assert.equal(init.method, "GET");
      return {
        status: 200,
        body: JSON.stringify({
          ok: true,
          miner_id: "alice",
          total: 1,
          transactions: [{ tx_hash: "abc123", amount: 5, type: "transfer_in" }]
        })
      };
    })
  });

  assert.deepEqual(await client.transferHistory("alice", { limit: 5 }), [
    { tx_hash: "abc123", amount: 5, type: "transfer_in" }
  ]);
});

test("normalizes legacy array transfer history responses", async () => {
  const client = new RustChainClient({
    fetch: mockFetch(() => ({
      status: 200,
      body: JSON.stringify([{ tx_hash: "legacy", amount: 1 }])
    }))
  });

  assert.deepEqual(await client.transferHistory("alice"), [{ tx_hash: "legacy", amount: 1 }]);
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
