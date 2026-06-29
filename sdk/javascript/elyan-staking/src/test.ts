import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  StakingClient,
  StakingValidationError,
  StakingError,
} from "./index.js";

// -------------------------------------------------------------------
// Unit tests (no network required)
// -------------------------------------------------------------------

describe("StakingClient", () => {
  it("accepts valid config with default fetch", () => {
    const client = new StakingClient({ apiKey: "test-key" });
    assert.ok(client);
  });
});

describe("validate arguments", () => {
  it("stake rejects empty skill", async () => {
    const client = new StakingClient();
    await assert.rejects(
      () => client.stake({ skill: "", bondRtc: 10 }),
      StakingValidationError,
    );
  });

  it("stake rejects zero bond", async () => {
    const client = new StakingClient();
    await assert.rejects(
      () => client.stake({ skill: "test", bondRtc: 0 }),
      StakingValidationError,
    );
  });

  it("stake rejects negative bond", async () => {
    const client = new StakingClient();
    await assert.rejects(
      () => client.stake({ skill: "test", bondRtc: -1 }),
      StakingValidationError,
    );
  });

  it("submit rejects empty taskId", async () => {
    const client = new StakingClient();
    await assert.rejects(
      () => client.submit({ taskId: "", result: { ok: true } }),
      StakingValidationError,
    );
  });

  it("poll rejects empty taskId", async () => {
    const client = new StakingClient();
    await assert.rejects(() => client.poll(""), StakingValidationError);
  });
});

// -------------------------------------------------------------------
// Network-dependent tests (requires live gate)
// -------------------------------------------------------------------

const LIVE_TESTS = process.env.TEST_LIVE === "1";

if (LIVE_TESTS) {
  describe("live gate (TEST_LIVE=1)", () => {
    const client = new StakingClient({
      baseUrl: process.env.GATE_URL ?? "https://gate.rustchain.org",
      apiKey: process.env.GATE_API_KEY ?? "",
    });

    it("stake returns a taskId", async () => {
      const res = await client.stake({ skill: "ping", bondRtc: 1 });
      assert.ok(res.taskId, "Expected a taskId");
      assert.match(res.status, /^(pending|accepted|rejected)$/);
    });

    it("stake → poll roundtrip", async () => {
      const { taskId } = await client.stake({
        skill: "ping",
        bondRtc: 1,
      });
      const polled = await client.poll(taskId);
      assert.ok(polled.taskId);
    });

    it("submit after stake", async () => {
      const { taskId } = await client.stake({
        skill: "ping",
        bondRtc: 1,
      });
      const submitRes = await client.submit({
        taskId,
        result: { output: "pong" },
      });
      assert.match(submitRes.status, /^(submitted|verified|rejected)$/);
    });
  });
} else {
  console.log(
    "ℹ️  Live tests skipped. Set TEST_LIVE=1 to run against a real gate.",
  );
}
