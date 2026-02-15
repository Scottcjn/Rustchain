import subprocess
import os

class BountyExecutor:
    """
    Handles the technical execution of a bounty: fork, clone, implement, commit, PR.
    """
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token

    def fork_and_clone(self):
        """Fork and clone the repository using gh CLI."""
        print(f"🍴 Forking {self.repo}...")
        subprocess.run(["gh", "repo", "fork", self.repo, "--clone=true"], check=True)

    def submit_pr(self, branch: str, title: str, body: str):
        """Create a PR to the upstream repository."""
        print(f"🚀 Creating Pull Request: {title}")
        subprocess.run([
            "gh", "pr", "create", 
            "--title", title, 
            "--body", body, 
            "--head", branch
        ], check=True)

    def commit_changes(self, message: str):
        """Commit local changes."""
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push", "origin", "HEAD"], check=True)
