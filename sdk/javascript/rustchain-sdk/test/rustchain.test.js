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
  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      assert.equal(url, "https://rustchain.org/wallet/transfer/signed");
      assert.equal(init.method, "POST");
      assert.deepEqual(JSON.parse(init.body), {
        from_address: "alice",
        to_address: "bob",
        amount_rtc: 1.25,
        fee_rtc: 0,
        signature: "sig123",
        public_key: "pk456",
        nonce: 7
      });
      return { status: 200, body: JSON.stringify({ success: true }) };
    })
  });

  assert.deepEqual(
    await client.transfer({ from: "alice", to: "bob", amount: 1.25, signature: "sig123", publicKey: "pk456", nonce: 7 }),
    { success: true }
  );
});

test("transfer defaults fee_rtc to 0", async () => {
  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      const body = JSON.parse(init.body);
      assert.equal(body.fee_rtc, 0);
      return { status: 200, body: JSON.stringify({ ok: true }) };
    })
  });

  await client.transfer({ from: "alice", to: "bob", amount: 5 });
});

test("transferHistory uses miner_id param and normalizes envelope", async () => {
  const client = new RustChainClient({
    fetch: mockFetch((url) => {
      assert.ok(url.includes("miner_id=alice"), "should use miner_id param");
      assert.ok(!url.includes("wallet="), "should not use wallet param");
      assert.ok(url.includes("limit=3"), "should pass limit");
      return {
        status: 200,
        body: JSON.stringify({ miner_id: "alice", ok: true, total: 1, transactions: [{ id: "tx1" }] })
      };
    })
  });

  const result = await client.transferHistory("alice", { limit: 3 });
  assert.deepEqual(result, [{ id: "tx1" }]);
});

test("transferHistory handles legacy bare-array responses", async () => {
  const client = new RustChainClient({
    fetch: mockFetch(() => ({
      status: 200,
      body: JSON.stringify([{ id: "tx1" }, { id: "tx2" }])
    }))
  });

  const result = await client.transferHistory("alice");
  assert.deepEqual(result, [{ id: "tx1" }, { id: "tx2" }]);
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
