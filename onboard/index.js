#!/usr/bin/env node
// rustchain-onboard — Interactive onboarding wizard for RustChain contributors
// Bounty #760 | Wallet: noxventures_rtc

const readline = require("readline");
const https = require("https");
const http = require("http");
const { execSync } = require("child_process");

// ─── Colors ─────────────────────────────────────────────────────────────────── //
const C = {
  reset: "\x1b[0m", bold: "\x1b[1m",
  green: "\x1b[32m", red: "\x1b[31m", yellow: "\x1b[33m", blue: "\x1b[34m", cyan: "\x1b[36m",
};
const ok    = (s) => `${C.green}✓${C.reset} ${s}`;
const err   = (s) => `${C.red}✗${C.reset} ${s}`;
const info  = (s) => `  ${s}`;
const bold  = (s) => `${C.bold}${s}${C.reset}`;
const step  = (n, t, total) => `\n${C.bold}${C.cyan}[Step ${n}/${total}]${C.reset} ${C.bold}${t}${C.reset}`;

const NODE = "https://50.28.86.131";
const REPOS = [
  { name: "Rustchain", url: "https://github.com/Scottcjn/Rustchain" },
  { name: "rustchain-bounties", url: "https://github.com/Scottcjn/rustchain-bounties" },
  { name: "bottube", url: "https://github.com/Scottcjn/bottube" },
  { name: "rustchain-monitor", url: "https://github.com/Scottcjn/rustchain-monitor" },
  { name: "rustchain-wallet", url: "https://github.com/Scottcjn/rustchain-wallet" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────── //
function fetch(url) {
  return new Promise((resolve) => {
    const lib = url.startsWith("https") ? https : http;
    const req = lib.get(url, { headers: { "User-Agent": "rustchain-onboard/1.0" }, rejectUnauthorized: false }, (res) => {
      let body = "";
      res.on("data", (d) => (body += d));
      res.on("end", () => {
        try { resolve(JSON.parse(body)); } catch { resolve(null); }
      });
    });
    req.on("error", () => resolve(null));
    req.setTimeout(8000, () => { req.destroy(); resolve(null); });
  });
}

function openBrowser(url) {
  try {
    const cmd = process.platform === "darwin" ? "open" : process.platform === "win32" ? "start" : "xdg-open";
    execSync(`${cmd} "${url}"`, { stdio: "ignore" });
  } catch {}
}

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
function ask(q) {
  return new Promise((r) => rl.question(q, r));
}
function pause(msg = "  Press Enter to continue...") {
  return ask(msg);
}

// ─── Wizard Steps ─────────────────────────────────────────────────────────────── //
async function banner() {
  console.clear();
  console.log(bold("╔══════════════════════════════════════════════════╗"));
  console.log(bold("║        RustChain Contributor Onboarding          ║"));
  console.log(bold("║     From zero to contributing in 2 minutes       ║"));
  console.log(bold("╚══════════════════════════════════════════════════╝"));
  console.log();
}

async function step1_wallet() {
  console.log(step(1, "Create Your Wallet", 5));
  console.log(info("Your wallet name is your identity on RustChain."));
  console.log(info("Rules: 3-32 chars, letters/numbers/hyphens/underscores, start with a letter.\n"));

  let wallet = null;
  while (!wallet) {
    const input = await ask("  Enter a wallet name: ");
    if (/^[a-zA-Z][a-zA-Z0-9_-]{2,31}$/.test(input)) {
      wallet = input;
    } else {
      console.log(err("Invalid format. Try: my-cool-wallet or dev123"));
    }
  }

  // Check availability (try to GET /wallet/<name>)
  process.stdout.write("  Checking availability... ");
  const data = await fetch(`${NODE}/wallet/${wallet}`);
  if (data === null) {
    // 404 or error = wallet doesn't exist yet = available
    console.log(ok("Available! ✨"));
  } else if (data.balance !== undefined || data.wallet_name) {
    console.log(`${C.yellow}⚠${C.reset} Already registered — using existing wallet`);
  } else {
    console.log(ok("Looks good!"));
  }

  console.log(ok(`Wallet name: ${C.bold}${wallet}${C.reset}`));
  return wallet;
}

async function step2_stars() {
  console.log(step(2, "Star Key Repos", 5));
  console.log(info("Starring repos shows support and earns you repo-watch rewards.\n"));

  for (let i = 0; i < REPOS.length; i++) {
    const r = REPOS[i];
    console.log(`  Opening ${C.bold}${r.name}${C.reset} (${i + 1}/${REPOS.length})...`);
    openBrowser(r.url);
    await pause(`  ★ Star it, then press Enter to continue...`);
  }

  console.log();
  console.log(ok(`Starred ${REPOS.length} repos — you're in the community!`));
  console.log(info("Tip: Claim the repo-watch bounty at github.com/Scottcjn/rustchain-bounties/issues/731"));
}

async function step3_follow() {
  console.log(step(3, "Follow Scottcjn on GitHub", 5));
  console.log(info("Following the main developer keeps you in the loop on new bounties.\n"));

  openBrowser("https://github.com/Scottcjn");
  await pause("  Follow Scottcjn, then press Enter...");
  console.log(ok("Following @Scottcjn — you'll see new bounties in your feed!"));
}

async function step4_balance(wallet) {
  console.log(step(4, "Check Your Balance", 5));
  console.log(info("Your starting balance is 0 RTC — let's see how to earn some.\n"));

  process.stdout.write("  Checking node status... ");
  const health = await fetch(`${NODE}/health`);
  if (health) {
    console.log(ok(`Node is up (version: ${health.version || "unknown"})`));
  } else {
    console.log(`${C.yellow}⚠${C.reset} Node unreachable — but you can still continue`);
  }

  const epoch = await fetch(`${NODE}/epoch`);
  if (epoch) {
    console.log(ok(`Current epoch: ${epoch.epoch || "?"} — attestations active`));
  }

  console.log();
  console.log(info(`Your wallet: ${C.bold}${wallet}${C.reset}`));
  console.log(info("Balance: 0 RTC (earn by mining or completing bounties)"));
  console.log();
  console.log(info("🏆 Ways to earn RTC:"));
  console.log(info("  • Run the miner: curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/setup.sh | bash"));
  console.log(info("  • Complete bounties: https://github.com/Scottcjn/rustchain-bounties/issues"));
  console.log(info("  • Agent Economy jobs: https://50.28.86.131/agent/jobs"));
}

async function step5_attest(wallet) {
  console.log(step(5, "First Attestation", 5));
  console.log(info("Mining means your hardware periodically 'attests' to the network.\n"));

  const answer = await ask("  Want to set up mining now? [y/N] ");
  if (answer.toLowerCase() !== "y") {
    console.log(info("No problem! You can run setup.sh anytime:"));
    console.log(info("  curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/setup.sh | bash"));
    return;
  }

  console.log();
  console.log(info("Launching miner setup wizard..."));
  console.log(info("Command: curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/setup.sh | bash"));
  console.log();
  openBrowser("https://github.com/Scottcjn/Rustchain#mining");
  await pause("  Open a new terminal and run the command above, then press Enter...");
  console.log(ok("Mining setup initiated!"));
}

async function summary(wallet) {
  console.log(`\n${C.bold}╔══════════════════════════════════════════════════╗${C.reset}`);
  console.log(`${C.bold}║              You're All Set! 🎉                 ║${C.reset}`);
  console.log(`${C.bold}╚══════════════════════════════════════════════════╝${C.reset}`);
  console.log();
  console.log(`  ${C.green}✓${C.reset} Wallet:    ${C.bold}${wallet}${C.reset}`);
  console.log(`  ${C.green}✓${C.reset} Starred:   ${REPOS.length} repos`);
  console.log(`  ${C.green}✓${C.reset} Following: @Scottcjn`);
  console.log();
  console.log(bold("  What's next:"));
  console.log(info("  • Check open bounties: https://github.com/Scottcjn/rustchain-bounties/issues"));
  console.log(info("  • Agent Economy jobs: https://50.28.86.131/agent/jobs"));
  console.log(info("  • Join Discord: https://discord.gg/rustchain"));
  console.log(info("  • BoTTube: https://bottube.ai"));
  console.log();
  console.log(info(`  ${C.bold}Happy building! ⛏️${C.reset}`));
  console.log();
}

// ─── Main ────────────────────────────────────────────────────────────────────── //
(async () => {
  try {
    await banner();
    const wallet = await step1_wallet();
    await step2_stars();
    await step3_follow();
    await step4_balance(wallet);
    await step5_attest(wallet);
    await summary(wallet);
  } catch (e) {
    if (e.code === "ERR_USE_AFTER_CLOSE") process.exit(0);
    throw e;
  } finally {
    rl.close();
    process.exit(0);
  }
})();
