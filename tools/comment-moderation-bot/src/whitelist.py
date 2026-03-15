"""
Whitelist Module.

Handles checking if users, organizations, or repositories are exempt from moderation.
"""

from dataclasses import dataclass
from typing import Optional

from .config import WhitelistConfig
from .github_client import GitHubClient


@dataclass
class WhitelistCheckResult:
    """Result of a whitelist check."""

    is_exempt: bool
    reason: str
    matched_rule: Optional[str] = None


class WhitelistChecker:
    """
    Checks if a comment author or repository is exempt from moderation.
    """

    def __init__(self, config: WhitelistConfig):
        self.config = config

        # Pre-parse whitelist values
        self.trusted_users = config.get_trusted_users()
        self.trusted_orgs = config.get_trusted_orgs()
        self.exempt_repos = config.get_exempt_repos()
        self.exempt_labels = config.get_exempt_labels()

        # Cache for user org membership
        self._user_orgs_cache: dict[str, set[str]] = {}

    def check_user(
        self,
        username: str,
        author_association: Optional[str] = None,
        user_orgs: Optional[set[str]] = None,
    ) -> WhitelistCheckResult:
        """
        Check if a user is exempt from moderation.

        Args:
            username: GitHub username
            author_association: Author's association with repo
            user_orgs: Set of organizations the user belongs to

        Returns:
            WhitelistCheckResult
        """
        username_normalized = username.lstrip("@").lower()

        # Check trusted users
        if username_normalized in {u.lower() for u in self.trusted_users}:
            return WhitelistCheckResult(
                is_exempt=True,
                reason=f"User '{username}' is in trusted users list",
                matched_rule="trusted_user",
            )

        # Check author association (OWNER, COLLABORATOR, MEMBER are typically trusted)
        trusted_associations = {"OWNER", "COLLABORATOR", "MEMBER", "CONTRIBUTOR"}
        if author_association and author_association.upper() in trusted_associations:
            return WhitelistCheckResult(
                is_exempt=True,
                reason=f"Author association '{author_association}' is trusted",
                matched_rule="trusted_association",
            )

        # Check trusted organizations
        if user_orgs:
            user_orgs_lower = {o.lower() for o in user_orgs}
            trusted_orgs_lower = {o.lower() for o in self.trusted_orgs}

            matching_orgs = user_orgs_lower & trusted_orgs_lower
            if matching_orgs:
                return WhitelistCheckResult(
                    is_exempt=True,
                    reason=f"User belongs to trusted org '{list(matching_orgs)[0]}'",
                    matched_rule="trusted_org",
                )

        return WhitelistCheckResult(
            is_exempt=False,
            reason="User is not whitelisted",
        )

    def check_repository(self, repo: str) -> WhitelistCheckResult:
        """
        Check if a repository is exempt from moderation.

        Args:
            repo: Repository name in format "owner/repo"

        Returns:
            WhitelistCheckResult
        """
        repo_normalized = repo.lower()

        # Check exempt repos
        for exempt_repo in self.exempt_repos:
            if exempt_repo.lower() == repo_normalized:
                return WhitelistCheckResult(
                    is_exempt=True,
                    reason=f"Repository '{repo}' is exempt",
                    matched_rule="exempt_repo",
                )

        return WhitelistCheckResult(
            is_exempt=False,
            reason="Repository is not exempt",
        )

    def check_issue_labels(
        self, issue_labels: list[str]
    ) -> WhitelistCheckResult:
        """
        Check if issue labels exempt comments from moderation.

        Args:
            issue_labels: List of label names on the issue

        Returns:
            WhitelistCheckResult
        """
        if not self.exempt_labels:
            return WhitelistCheckResult(
                is_exempt=False,
                reason="No exempt labels configured",
            )

        issue_labels_lower = {label.lower() for label in issue_labels}
        exempt_labels_lower = {label.lower() for label in self.exempt_labels}

        matching_labels = issue_labels_lower & exempt_labels_lower
        if matching_labels:
            return WhitelistCheckResult(
                is_exempt=True,
                reason=f"Issue has exempt label '{list(matching_labels)[0]}'",
                matched_rule="exempt_label",
            )

        return WhitelistCheckResult(
            is_exempt=False,
            reason="Issue has no exempt labels",
        )

    async def check_with_github(
        self,
        username: str,
        repo: str,
        issue_labels: list[str],
        github_client: GitHubClient,
        installation_id: int,
    ) -> WhitelistCheckResult:
        """
        Perform comprehensive whitelist check using GitHub API.

        Args:
            username: Comment author username
            repo: Repository name
            issue_labels: Issue labels
            github_client: GitHub API client
            installation_id: Installation ID

        Returns:
            WhitelistCheckResult
        """
        # Check repository exemption first (no API call needed)
        repo_result = self.check_repository(repo)
        if repo_result.is_exempt:
            return repo_result

        # Check issue labels
        label_result = self.check_issue_labels(issue_labels)
        if label_result.is_exempt:
            return label_result

        # Check user with GitHub API for org membership
        try:
            user_orgs = await github_client.get_user_orgs(username, installation_id)
            user_orgs_set = set(user_orgs)

            # Cache for future checks
            self._user_orgs_cache[username.lower()] = user_orgs_set

            user_result = self.check_user(
                username,
                user_orgs=user_orgs_set,
            )
            return user_result

        except Exception:
            # If API call fails, do basic check without org info
            return self.check_user(username)

    def is_bot_user(self, username: str) -> bool:
        """Check if username appears to be a bot account."""
        username_lower = username.lower()

        # GitHub bot indicator
        if username_lower.endswith("[bot]"):
            return True

        # Common bot patterns
        bot_patterns = [
            "bot",
            "automation",
            "ci",
            "cd",
            "dependabot",
            "renovate",
            "probot",
        ]

        return any(pattern in username_lower for pattern in bot_patterns)
