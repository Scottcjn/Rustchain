#!/usr/bin/env python3
"""
RustChain Autonomous Bounty Hunter Agent
Bounty: #2861 — 50 RTC
Author: yw13931835525-cyber (Yuanbao Agent)
"""

import json, os, sys, time, argparse, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
from github import Github
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
RTC_WALLET = os.getenv("RTC_WALLET", "yw13931835525@gmail.com")
AGENT_NAME = os.getenv("AGENT_NAME", "yuanbao-agent")

GITHUB_ORG = "Scottcjn"
GITHUB_REPO = "Rustchain"
BOUNTIES_ORG = "Scottcjn"
BOUNTIES_REPO = "rustchain-bounties"
FORK_USER = os.getenv("GITHUB_USER", "yw13931835525-cyber")

LABEL_PRIORITY = {"good first issue": 3, "easy": 2, "standard": 2, "major": 1, "critical": 0, "help wanted": 1}
MIN_BOUNTY_RTC = 5
SCAN_INTERVAL = 300


def get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def get_github() -> Github:
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not set")
    return Github(GITHUB_TOKEN)


def llm_evaluate(client: anthropic.Anthropic, bounty: dict) -> dict:
    """Evaluate bounty feasibility using LLM."""
    prompt = f"""You are an AI agent evaluating RustChain bounty #{bounty['number']}.

Bounty: {bounty['title']}
Labels: {', '.join(bounty.get('labels', []))}
Reward: {bounty.get('reward_rtc', 0)} RTC
Body: {bounty.get('body', '')[:600]}

Your skills: Python, TypeScript, Go, Rust, Solidity, GitHub API automation, Claude Code integration, blockchain/smart contracts.

Return ONLY valid JSON: {{"feasible": true/false, "score": 0.0-1.0, "approach": "brief approach in 1 sentence", "reason": "1 sentence"}}
"""
    try:
        resp = client.messages.create(
            model="claude-opus-4-5", max_tokens=384, temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if "{" in text:
            j = text[text.index("{"):text.rindex("}")+1]
            return json.loads(j)
    except Exception as e:
        pass
    return {"feasible": False, "score": 0.0, "approach": "error", "reason": str(e)}


def llm_generate(client: anthropic.Anthropic, bounty: dict, context_files: dict) -> str:
    """Generate implementation via LLM."""
    prompt = f"""Implement RustChain bounty #{bounty['number']}: {bounty['title']}

Requirements:
{bounty.get('body', '')[:2500]}

Existing files:
"""
    for fname, content in list(context_files.items())[:5]:
        prompt += f"\n### {fname}\n{content[:1500]}\n"
    prompt += "\n\nReturn FILENAME blocks and a COMMIT message."

    try:
        resp = client.messages.create(
            model="claude-opus-4-5", max_tokens=8192, temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        raise RuntimeError(f"LLM generation failed: {e}")


def scan_bounties(gh_client: Github, labels=None) -> list[dict]:
    """Scan open bounties from rustchain-bounties repo."""
    import re
    repo = gh_client.get_repo(f"{BOUNTIES_ORG}/{BOUNTIES_REPO}")
    issues = repo.get_issues(state="open")

    bounties = []
    for issue in issues:
        if issue.pull_request:
            continue
        body = issue.body or ""
        if "bounty" not in body.lower():
            continue

        rtc_match = re.search(r'(\d+)\s*RTC', body, re.IGNORECASE)
        rtc = int(rtc_match.group(1)) if rtc_match else 0

        bounties.append({
            "number": issue.number, "title": issue.title, "body": body,
            "labels": [l.name for l in issue.labels],
            "reward_rtc": rtc, "state": issue.state,
            "created_at": issue.created_at.isoformat(),
            "comments": issue.comments,
            "assignees": [a.login for a in issue.assignees],
        })
    return bounties


def get_ext(fname: str) -> str:
    e = (fname.rsplit(".", 1)[-1] if "." in fname else "")
    return {"py": "python", "ts": "typescript", "js": "javascript", "md": "markdown"}.get(e, "")


class BountyHunterAgent:
    def __init__(self, gh: Github, llm):
        self.gh = gh
        self.llm = llm
        self.earnings = {"total_earned_rtc": 0.0, "bounties_completed": [], "last_run": None}

    def scan_and_evaluate(self, max_value=None, labels=None) -> list[dict]:
        bounties = scan_bounties(self.gh, labels)
        if max_value:
            bounties = [b for b in bounties if b["reward_rtc"] <= max_value]
        bounties = [b for b in bounties if b["reward_rtc"] >= MIN_BOUNTY_RTC]

        def priority(b):
            p = max((LABEL_PRIORITY.get(l, 1) for l in b["labels"]), default=1)
            return -(b["reward_rtc"] * p)
        bounties.sort(key=priority)

        evaluated = []
        for bounty in bounties[:8]:
            print(f"[EVAL] #{bounty['number']} — {bounty['title'][:50]} ({bounty['reward_rtc']} RTC)")
            try:
                result = llm_evaluate(self.llm, bounty)
                bounty["evaluation"] = result
                if result["feasible"]:
                    evaluated.append(bounty)
                    print(f"  -> FEASIBLE score={result['score']:.2f}: {result['approach']}")
                else:
                    print(f"  -> NOT FEASIBLE: {result['reason']}")
            except Exception as e:
                print(f"  -> ERROR: {e}")
        return evaluated

    def execute_bounty(self, bounty: dict) -> bool:
        """Execute a single bounty: fork, implement, PR."""
        print(f"\n[EXEC] Bounty #{bounty['number']}")

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "repo"
            try:
                # Fork if needed
                repo = self.gh.get_repo(f"{GITHUB_ORG}/{GITHUB_REPO}")
                try:
                    fork = self.gh.get_user().create_fork(repo)
                    time.sleep(5)
                except Exception:
                    forks = [f for f in self.gh.get_user().get_repos() if f.name == GITHUB_REPO]
                    fork = forks[0] if forks else None

                if not fork:
                    print("[EXEC] Could not create/find fork")
                    return False

                subprocess.run(["git", "clone", fork.clone_url, str(target)], check=True, capture_output=True)

                # Gather context
                context = {"README.md": "See RustChain repo README"}
                try:
                    r = self.gh.get_repo(f"{GITHUB_ORG}/{GITHUB_REPO}")
                    for c in r.get_contents(""):
                        if c.name in ["README.md", "setup.py", "pyproject.toml"] and c.size < 50000:
                            context[c.name] = c.decoded_content.decode()[:2000]
                except Exception:
                    pass

                # Generate
                result = llm_generate(self.llm, bounty, context)
                files, commit_msg = self._parse_result(result)

                for fname, content in files.items():
                    (target / fname).parent.mkdir(parents=True, exist_ok=True)
                    (target / fname).write_text(content)

                # Commit and push
                branch = f"bounty-{bounty['number']}-{int(time.time())}"
                subprocess.run(["git", "checkout", "-b", branch], cwd=target, check=True, capture_output=True)
                subprocess.run(["git", "config", "user.email", "yuanbao@openclaw.ai"], cwd=target, check=True)
                subprocess.run(["git", "config", "user.name", AGENT_NAME], cwd=target, check=True)
                subprocess.run(["git", "add", "-A"], cwd=target, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=target, check=True, capture_output=True)
                subprocess.run(
                    ["git", "push", "-u", fork.clone_url.replace("https://", f"https://{GITHUB_TOKEN}@"), branch],
                    cwd=target, check=True, capture_output=True, env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN}
                )

                # Create PR
                main_repo = self.gh.get_repo(f"{GITHUB_ORG}/{GITHUB_REPO}")
                pr_body = f"""## Bounty Claim

**Bounty:** #{bounty['number']} — {bounty['title']}
**Reward:** {bounty['reward_rtc']} RTC

### What I Built
{bounty.get('evaluation', {}).get('approach', 'Implementation per bounty requirements.')}

**Wallet:** `{RTC_WALLET}`
"""
                pr = main_repo.create_pull(
                    title=f"[BOUNTY #{bounty['number']}] {bounty['title'][:100]}",
                    body=pr_body,
                    head=f"{FORK_USER}:{branch}",
                    base="main",
                )

                # Comment on bounty issue
                try:
                    issue = self.gh.get_repo(f"{BOUNTIES_ORG}/{BOUNTIES_REPO}").get_issue(bounty["number"])
                    issue.create_comment(
                        f"## Bounty Claimed by {AGENT_NAME}\n\n"
                        f"**PR:** {pr.html_url}\n**Reward:** {bounty['reward_rtc']} RTC\n"
                        f"**Wallet:** `{RTC_WALLET}`\n\n"
                        f"Agent has autonomously implemented and submitted the solution. Ready for review!"
                    )
                except Exception:
                    pass

                print(f"[SUCCESS] PR: {pr.html_url}")
                self.earnings["bounties_completed"].append(bounty["number"])
                self.earnings["last_run"] = datetime.now(timezone.utc).isoformat()
                return True

            except Exception as e:
                print(f"[EXEC] Failed: {e}")
                import traceback; traceback.print_exc()

        return False

    def _parse_result(self, content: str) -> tuple[dict, str]:
        """Parse LLM output into {filename: content} and commit message."""
        files = {}
        commit_msg = "feat: implement bounty solution"
        parts = content.split("FILENAME:")
        for part in parts[1:]:
            lines = part.strip().split("\n", 1)
            if not lines:
                continue
            fname = lines[0].strip()
            text = lines[1] if len(lines) > 1 else ""
            if not fname:
                continue
            code_start = text.index("```") + 3 if "```" in text else -1
            if code_start > 2:
                code_end = text.rindex("```")
                lang = text[3:code_start-3].strip()
                code = text[code_start:code_end]
                files[fname] = code
            if "COMMIT:" in text:
                for line in text.split("\n"):
                    if line.startswith("COMMIT:"):
                        commit_msg = line.split("COMMIT:", 1)[1].strip()
                        break
        return files, commit_msg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--bounty-id", type=int)
    parser.add_argument("--max-value", type=int)
    parser.add_argument("--labels", type=str)
    args = parser.parse_args()

    gh = get_github()
    llm = get_client()
    agent = BountyHunterAgent(gh, llm)

    if args.bounty_id:
        agent.execute_bounty({"number": args.bounty_id, "title": "N/A", "body": "N/A", "labels": [], "reward_rtc": 0})
    else:
        labels = args.labels.split(",") if args.labels else None
        while True:
            candidates = agent.scan_and_evaluate(max_value=args.max_value, labels=labels)
            if candidates:
                best = max(candidates, key=lambda b: b["evaluation"]["score"])
                agent.execute_bounty(best)
            if not args.daemon:
                break
            print(f"[SLEEP] {SCAN_INTERVAL}s before next scan...")
            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
