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

test("lists agent jobs with pagination and filters", async () => {
  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      assert.equal(url, "https://rustchain.org/agent/jobs?category=code&status=open&limit=10&offset=2&min_reward=5");
      assert.equal(init.method, "GET");
      return { status: 200, body: JSON.stringify({ ok: true, jobs: [{ job_id: "job-1" }], total: 1 }) };
    })
  });

  assert.deepEqual(await client.listJobs({ category: "code", status: "open", limit: 10, offset: 2, minReward: 5 }), {
    ok: true,
    jobs: [{ job_id: "job-1" }],
    total: 1
  });
});

test("posts an agent job with the RIP-302 payload", async () => {
  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      assert.equal(url, "https://rustchain.org/agent/jobs");
      assert.equal(init.method, "POST");
      assert.deepEqual(JSON.parse(init.body), {
        poster_wallet: "RTCposter",
        title: "Find a useful product",
        description: "Research and compare three useful products for a client.",
        category: "research",
        reward_rtc: 12.5,
        ttl_seconds: 86400,
        tags: ["research", "shopping"]
      });
      return { status: 201, body: JSON.stringify({ ok: true, job_id: "job-1" }) };
    })
  });

  assert.deepEqual(await client.postJob({
    posterWallet: "RTCposter",
    title: "Find a useful product",
    description: "Research and compare three useful products for a client.",
    category: "research",
    rewardRtc: 12.5,
    ttlSeconds: 86400,
    tags: ["research", "shopping"]
  }), { ok: true, job_id: "job-1" });
});

test("supports the RIP-302 job lifecycle endpoints", async () => {
  const calls = [];
  const client = new RustChainClient({
    fetch: mockFetch((url, init) => {
      calls.push({ url, method: init.method, body: init.body ? JSON.parse(init.body) : undefined });
      return { status: 200, body: JSON.stringify({ ok: true }) };
    })
  });

  await client.getJob("job/1");
  await client.claimJob("job/1", "RTCworker");
  await client.deliverJob("job/1", {
    workerWallet: "RTCworker",
    deliverableUrl: "https://example.test/result",
    deliverableHash: "sha256:abc",
    resultSummary: "Completed"
  });
  await client.acceptJob("job/1", { posterWallet: "RTCposter", rating: 5 });
  await client.disputeJob("job/1", "RTCposter", "Needs review");
  await client.cancelJob("job/1", "RTCposter");
  await client.reputation("RTCworker/id");
  await client.agentStats();

  assert.deepEqual(calls, [
    { url: "https://rustchain.org/agent/jobs/job%2F1", method: "GET", body: undefined },
    { url: "https://rustchain.org/agent/jobs/job%2F1/claim", method: "POST", body: { worker_wallet: "RTCworker" } },
    {
      url: "https://rustchain.org/agent/jobs/job%2F1/deliver",
      method: "POST",
      body: {
        worker_wallet: "RTCworker",
        deliverable_url: "https://example.test/result",
        deliverable_hash: "sha256:abc",
        result_summary: "Completed"
      }
    },
    { url: "https://rustchain.org/agent/jobs/job%2F1/accept", method: "POST", body: { poster_wallet: "RTCposter", rating: 5 } },
    { url: "https://rustchain.org/agent/jobs/job%2F1/dispute", method: "POST", body: { poster_wallet: "RTCposter", reason: "Needs review" } },
    { url: "https://rustchain.org/agent/jobs/job%2F1/cancel", method: "POST", body: { poster_wallet: "RTCposter" } },
    { url: "https://rustchain.org/agent/reputation/RTCworker%2Fid", method: "GET", body: undefined },
    { url: "https://rustchain.org/agent/stats", method: "GET", body: undefined }
  ]);
});

test("validates agent job inputs before making requests", async () => {
  const client = new RustChainClient({ fetch: mockFetch(() => ({ status: 200 })) });

  await assert.rejects(
    () => client.postJob({ posterWallet: "RTCposter", title: "No", description: "This description is long enough.", category: "code", rewardRtc: 1, ttlSeconds: 3600 }),
    RustChainValidationError
  );
  await assert.rejects(() => client.listJobs({ category: "invalid" }), RustChainValidationError);
  await assert.rejects(() => client.deliverJob("job-1", { workerWallet: "RTCworker" }), RustChainValidationError);
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
