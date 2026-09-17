const assert = require("assert");
const { AgentEconomyClient } = require("../dist/src/index.js");

async function runTests() {
  console.log("Starting TypeScript Agent Economy SDK Test Suite...");

  const client = new AgentEconomyClient({ nodeUrl: "http://127.0.0.1:9999", timeoutMs: 1000 });

  // 1. Validation tests
  console.log("[1/5] Testing validation bounds on postJob...");
  await assert.rejects(
    async () => {
      await client.postJob({
        poster_wallet: "",
        title: "Test",
        category: "code",
        reward_rtc: 5
      });
    },
    /Missing required fields/
  );

  await assert.rejects(
    async () => {
      await client.postJob({
        poster_wallet: "RTC123",
        title: "Test",
        category: "code",
        reward_rtc: 0
      });
    },
    /Reward must be strictly positive/
  );

  // 2. Deliverable validation
  console.log("[2/5] Testing deliverJob validation...");
  await assert.rejects(
    async () => {
      await client.deliverJob("job_01", {
        worker_wallet: "RTC_worker"
      });
    },
    /Either deliverable_url or result_summary must be provided/
  );

  // 3. Accept rating bounds
  console.log("[3/5] Testing acceptJob rating range validation...");
  await assert.rejects(
    async () => {
      await client.acceptJob("job_01", {
        poster_wallet: "RTC_poster",
        rating: 6
      });
    },
    /Rating must be between 1 and 5/
  );

  // 4. Dispute validation
  console.log("[4/5] Testing disputeJob reason requirement...");
  await assert.rejects(
    async () => {
      await client.disputeJob("job_01", {
        poster_wallet: "RTC_poster",
        reason: ""
      });
    },
    /jobId, poster_wallet, and dispute reason are required/
  );

  // 5. Reputation validation
  console.log("[5/5] Testing getReputation wallet validation...");
  await assert.rejects(
    async () => {
      await client.getReputation("");
    },
    /wallet address is required/
  );

  console.log("All 5/5 TypeScript Agent Economy SDK test suites PASSED!");
}

runTests().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
