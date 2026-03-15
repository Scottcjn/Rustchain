import { RustChainClient, RustChainError } from "../src";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(status: number, body: unknown): jest.Mock {
  return jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

function client(fetch: jest.Mock): RustChainClient {
  return new RustChainClient({
    baseUrl: "http://localhost:8099",
    adminKey: "test-admin-key",
    fetch: fetch as unknown as typeof globalThis.fetch,
  });
}

function lastCall(fetch: jest.Mock) {
  const [url, init] = fetch.mock.calls[fetch.mock.calls.length - 1];
  return { url: url as string, init: init as RequestInit };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RustChainClient", () => {
  // -----------------------------------------------------------------------
  // Health & Status
  // -----------------------------------------------------------------------

  it("health() sends GET /health", async () => {
    const body = { ok: true, version: "2.2.1", uptime_s: 100 };
    const f = mockFetch(200, body);
    const res = await client(f).health();
    expect(res).toEqual(body);
    expect(lastCall(f).url).toBe("http://localhost:8099/health");
    expect(lastCall(f).init.method).toBe("GET");
  });

  it("ready() sends GET /ready", async () => {
    const body = { ready: true, version: "2.2.1" };
    const f = mockFetch(200, body);
    const res = await client(f).ready();
    expect(res).toEqual(body);
  });

  it("stats() sends GET /api/stats", async () => {
    const body = {
      version: "2.2.1",
      chain_id: "rustchain-mainnet-candidate",
      epoch: 42,
      block_time: 600,
      total_miners: 150,
      total_balance: 96673.0,
      pending_withdrawals: 3,
      features: [],
      security: [],
    };
    const f = mockFetch(200, body);
    const res = await client(f).stats();
    expect(res.epoch).toBe(42);
  });

  // -----------------------------------------------------------------------
  // Error handling
  // -----------------------------------------------------------------------

  it("throws RustChainError on non-2xx response", async () => {
    const f = mockFetch(404, { error: "not_found" });
    await expect(client(f).health()).rejects.toThrow(RustChainError);
    await expect(client(f).health()).rejects.toMatchObject({ status: 404 });
  });

  // -----------------------------------------------------------------------
  // Epochs
  // -----------------------------------------------------------------------

  it("epoch() sends GET /epoch", async () => {
    const body = {
      epoch: 42,
      slot: 25200,
      epoch_pot: 1.5,
      enrolled_miners: 12,
      blocks_per_epoch: 600,
      total_supply_rtc: 21000000,
    };
    const f = mockFetch(200, body);
    const res = await client(f).epoch();
    expect(res.epoch).toBe(42);
    expect(res.total_supply_rtc).toBe(21000000);
  });

  it("epochEnroll() sends POST /epoch/enroll", async () => {
    const body = {
      ok: true,
      epoch: 42,
      weight: 2.0,
      hw_weight: 2.0,
      fingerprint_failed: false,
      miner_pk: "RTCabc",
      miner_id: "g4-powerbook-01",
    };
    const f = mockFetch(200, body);
    const res = await client(f).epochEnroll({
      miner_pubkey: "RTCabc",
      miner_id: "g4-powerbook-01",
      device: { family: "powerpc", arch: "g4" },
    });
    expect(res.ok).toBe(true);
    expect(lastCall(f).init.method).toBe("POST");
  });

  it("lotteryEligibility() includes miner_id query param", async () => {
    const body = {
      eligible: true,
      miner_id: "g4-pb",
      slot: 100,
      reason: "round_robin_selected",
    };
    const f = mockFetch(200, body);
    await client(f).lotteryEligibility("g4-pb");
    expect(lastCall(f).url).toContain("miner_id=g4-pb");
  });

  // -----------------------------------------------------------------------
  // Wallet & Balance
  // -----------------------------------------------------------------------

  it("walletBalance() sends GET /wallet/balance with query", async () => {
    const body = { miner_id: "test", amount_i64: 1000000, amount_rtc: 1.0 };
    const f = mockFetch(200, body);
    const res = await client(f).walletBalance("test");
    expect(res.amount_rtc).toBe(1.0);
    expect(lastCall(f).url).toContain("miner_id=test");
  });

  it("signedTransfer() sends POST /wallet/transfer/signed", async () => {
    const body = {
      ok: true,
      verified: true,
      signature_type: "Ed25519",
      replay_protected: true,
      phase: "pending",
      pending_id: 1,
      tx_hash: "abc",
      from_address: "RTCa",
      to_address: "RTCb",
      amount_rtc: 10,
      chain_id: "rustchain-mainnet-candidate",
      confirms_at: 0,
      confirms_in_hours: 24,
      message: "pending",
    };
    const f = mockFetch(200, body);
    const res = await client(f).signedTransfer({
      from_address: "RTCa",
      to_address: "RTCb",
      amount_rtc: 10,
      nonce: "123",
      signature: "sig",
      public_key: "pk",
    });
    expect(res.verified).toBe(true);
    expect(res.phase).toBe("pending");
  });

  it("balanceByPk() sends GET /balance/:pk", async () => {
    const body = { miner_pk: "RTCabc", balance_rtc: 42.5, amount_i64: 42500000 };
    const f = mockFetch(200, body);
    const res = await client(f).balanceByPk("RTCabc");
    expect(res.balance_rtc).toBe(42.5);
    expect(lastCall(f).url).toContain("/balance/RTCabc");
  });

  // -----------------------------------------------------------------------
  // Admin endpoints — header checks
  // -----------------------------------------------------------------------

  it("adminTransfer() sends X-Admin-Key header", async () => {
    const body = {
      ok: true,
      phase: "pending",
      pending_id: 1,
      tx_hash: "abc",
      from_miner: "a",
      to_miner: "b",
      amount_rtc: 5,
      confirms_at: 0,
      confirms_in_hours: 24,
      message: "pending",
    };
    const f = mockFetch(200, body);
    await client(f).adminTransfer({
      from_miner: "a",
      to_miner: "b",
      amount_rtc: 5,
      reason: "bounty",
    });
    const { init } = lastCall(f);
    expect((init.headers as Record<string, string>)["X-Admin-Key"]).toBe(
      "test-admin-key",
    );
  });

  it("allBalances() sends X-API-Key header", async () => {
    const body = { ok: true, count: 0, balances: [] };
    const f = mockFetch(200, body);
    await client(f).allBalances(10);
    const { init, url } = lastCall(f);
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe(
      "test-admin-key",
    );
    expect(url).toContain("limit=10");
  });

  // -----------------------------------------------------------------------
  // Attestation
  // -----------------------------------------------------------------------

  it("attestChallenge() sends POST /attest/challenge", async () => {
    const body = { nonce: "abc", expires_at: 100, server_time: 50 };
    const f = mockFetch(200, body);
    const res = await client(f).attestChallenge();
    expect(res.nonce).toBe("abc");
    expect(lastCall(f).init.method).toBe("POST");
  });

  // -----------------------------------------------------------------------
  // Block Headers
  // -----------------------------------------------------------------------

  it("chainTip() sends GET /headers/tip", async () => {
    const body = { slot: 100, miner: "test", tip_age: 5, signature_prefix: "ab" };
    const f = mockFetch(200, body);
    const res = await client(f).chainTip();
    expect(res.slot).toBe(100);
  });

  // -----------------------------------------------------------------------
  // Governance
  // -----------------------------------------------------------------------

  it("govProposals() sends GET /governance/proposals", async () => {
    const body = { ok: true, count: 0, proposals: [] };
    const f = mockFetch(200, body);
    const res = await client(f).govProposals();
    expect(res.count).toBe(0);
  });

  it("govVote() sends POST /governance/vote", async () => {
    const body = {
      ok: true,
      proposal_id: 1,
      voter_wallet: "RTCx",
      vote: "yes",
      base_balance_rtc: 10,
      antiquity_multiplier: 2,
      vote_weight: 20,
      status: "active",
      yes_weight: 20,
      no_weight: 0,
      result: "pending",
    };
    const f = mockFetch(200, body);
    const res = await client(f).govVote({
      proposal_id: 1,
      wallet: "RTCx",
      vote: "yes",
      nonce: "n1",
      signature: "sig",
      public_key: "pk",
    });
    expect(res.vote_weight).toBe(20);
  });

  // -----------------------------------------------------------------------
  // Withdrawals
  // -----------------------------------------------------------------------

  it("withdrawStatus() sends GET /withdraw/status/:id", async () => {
    const body = {
      withdrawal_id: "WD_123",
      miner_pk: "RTCa",
      amount: 10,
      fee: 0.01,
      destination: "5Grwva",
      status: "pending",
      created_at: 100,
      processed_at: null,
      tx_hash: null,
      error_msg: null,
    };
    const f = mockFetch(200, body);
    const res = await client(f).withdrawStatus("WD_123");
    expect(res.status).toBe("pending");
    expect(lastCall(f).url).toContain("/withdraw/status/WD_123");
  });

  it("feePool() sends GET /api/fee_pool", async () => {
    const body = {
      rip: 301,
      description: "Fee Pool",
      total_fees_collected_rtc: 1.5,
      total_fee_events: 150,
      fees_by_source: {},
      destination: "founder_community",
      destination_balance_rtc: 96671.5,
      withdrawal_fee_rtc: 0.01,
      recent_events: [],
    };
    const f = mockFetch(200, body);
    const res = await client(f).feePool();
    expect(res.rip).toBe(301);
  });

  // -----------------------------------------------------------------------
  // Beacon
  // -----------------------------------------------------------------------

  it("beaconSubmit() sends POST /beacon/submit", async () => {
    const body = { ok: true, envelope_id: 42 };
    const f = mockFetch(200, body);
    const res = await client(f).beaconSubmit({
      agent_id: "bcn_test",
      kind: "heartbeat",
      nonce: "nonce123",
      sig: "abcdef",
      pubkey: "pk",
    });
    expect(res.envelope_id).toBe(42);
  });

  it("beaconDigest() sends GET /beacon/digest", async () => {
    const body = { ok: true, digest: "sha256abc", count: 1000, latest_ts: 100 };
    const f = mockFetch(200, body);
    const res = await client(f).beaconDigest();
    expect(res.count).toBe(1000);
  });

  // -----------------------------------------------------------------------
  // Miners
  // -----------------------------------------------------------------------

  it("miners() sends GET /api/miners", async () => {
    const body = [
      {
        miner: "g4-pb",
        last_attest: 100,
        first_attest: 50,
        device_family: "powerpc",
        device_arch: "g4",
        hardware_type: "PowerPC G4",
        entropy_score: 0.85,
        antiquity_multiplier: 2.0,
      },
    ];
    const f = mockFetch(200, body);
    const res = await client(f).miners();
    expect(res).toHaveLength(1);
    expect(res[0].miner).toBe("g4-pb");
  });

  it("bountyMultiplier() sends GET /api/bounty-multiplier", async () => {
    const body = {
      ok: true,
      decay_model: "half-life",
      half_life_rtc: 25000,
      initial_fund_rtc: 96673,
      total_paid_rtc: 5000,
      remaining_rtc: 91673,
      current_multiplier: 0.87,
      current_multiplier_pct: "87%",
      example: { face_value: 100, actual_payout: 87, note: "test" },
      milestones: [],
    };
    const f = mockFetch(200, body);
    const res = await client(f).bountyMultiplier();
    expect(res.current_multiplier).toBe(0.87);
  });

  // -----------------------------------------------------------------------
  // P2P
  // -----------------------------------------------------------------------

  it("p2pPing() sends POST /p2p/ping", async () => {
    const body = { ok: true, timestamp: 123 };
    const f = mockFetch(200, body);
    const res = await client(f).p2pPing();
    expect(res.ok).toBe(true);
    expect(lastCall(f).init.method).toBe("POST");
  });

  // -----------------------------------------------------------------------
  // Trailing slash removal
  // -----------------------------------------------------------------------

  it("strips trailing slashes from baseUrl", async () => {
    const f = mockFetch(200, { ok: true });
    const c = new RustChainClient({
      baseUrl: "http://localhost:8099///",
      fetch: f as unknown as typeof globalThis.fetch,
    });
    await c.health();
    expect(lastCall(f).url).toBe("http://localhost:8099/health");
  });
});
