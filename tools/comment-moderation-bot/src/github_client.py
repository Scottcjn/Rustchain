"""
GitHub API Client.

Provides methods for interacting with GitHub API for comment moderation.
"""

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .github_auth import GitHubAuth


@dataclass
class CommentData:
    """Data about a GitHub comment."""

    id: int
    body: str
    author_login: str
    author_association: str
    created_at: str
    updated_at: str
    issue_url: str
    html_url: str


@dataclass
class IssueData:
    """Data about a GitHub issue."""

    number: int
    title: str
    state: str
    labels: list[str]
    created_at: str
    comments_count: int


class GitHubClient:
    """
    GitHub API client for comment moderation operations.
    """

    def __init__(
        self,
        auth: GitHubAuth,
        api_base_url: str = "https://api.github.com",
    ):
        self.auth = auth
        self.api_base_url = api_base_url.rstrip("/")

    async def _request(
        self,
        method: str,
        endpoint: str,
        installation_id: int,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make an authenticated API request."""
        headers = await self.auth.get_auth_headers(installation_id)

        url = f"{self.api_base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=data,
                params=params,
                timeout=30.0,
            )
            return response

    async def get_comment(
        self, repo_owner: str, repo_name: str, comment_id: int, installation_id: int
    ) -> CommentData:
        """
        Get a specific comment.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            comment_id: Comment ID
            installation_id: Installation ID for auth

        Returns:
            CommentData object
        """
        endpoint = f"/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}"
        response = await self._request("GET", endpoint, installation_id)
        response.raise_for_status()
        data = response.json()

        return CommentData(
            id=data["id"],
            body=data["body"] or "",
            author_login=data["user"]["login"],
            author_association=data["author_association"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            issue_url=data["issue_url"],
            html_url=data["html_url"],
        )

    async def delete_comment(
        self, repo_owner: str, repo_name: str, comment_id: int, installation_id: int
    ) -> bool:
        """
        Delete a comment.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            comment_id: Comment ID
            installation_id: Installation ID for auth

        Returns:
            True if deletion was successful
        """
        endpoint = f"/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}"
        response = await self._request("DELETE", endpoint, installation_id)

        # GitHub returns 204 No Content on successful deletion
        return response.status_code == 204

    async def get_issue(
        self, repo_owner: str, repo_name: str, issue_number: int, installation_id: int
    ) -> IssueData:
        """
        Get issue details.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            issue_number: Issue number
            installation_id: Installation ID for auth

        Returns:
            IssueData object
        """
        endpoint = f"/repos/{repo_owner}/{repo_name}/issues/{issue_number}"
        response = await self._request("GET", endpoint, installation_id)
        response.raise_for_status()
        data = response.json()

        return IssueData(
            number=data["number"],
            title=data["title"],
            state=data["state"],
            labels=[label["name"] for label in data.get("labels", [])],
            created_at=data["created_at"],
            comments_count=data.get("comments", 0),
        )

    async def get_issue_comments(
        self,
        repo_owner: str,
        repo_name: str,
        issue_number: int,
        installation_id: int,
        per_page: int = 100,
    ) -> list[CommentData]:
        """
        Get all comments on an issue.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            issue_number: Issue number
            installation_id: Installation ID for auth
            per_page: Results per page

        Returns:
            List of CommentData objects
        """
        endpoint = f"/repos/{repo_owner}/{repo_name}/issues/{issue_number}/comments"
        comments = []

        page = 1
        while True:
            response = await self._request(
                "GET",
                endpoint,
                installation_id,
                params={"per_page": per_page, "page": page},
            )
            response.raise_for_status()
            page_data = response.json()

            if not page_data:
                break

            for data in page_data:
                comments.append(
                    CommentData(
                        id=data["id"],
                        body=data["body"] or "",
                        author_login=data["user"]["login"],
                        author_association=data["author_association"],
                        created_at=data["created_at"],
                        updated_at=data["updated_at"],
                        issue_url=data["issue_url"],
                        html_url=data["html_url"],
                    )
                )

            page += 1

        return comments

    async def get_user_orgs(
        self, username: str, installation_id: int
    ) -> list[str]:
        """
        Get organizations a user belongs to.

        Args:
            username: GitHub username
            installation_id: Installation ID for auth

        Returns:
            List of organization names
        """
        endpoint = f"/users/{username}/orgs"
        response = await self._request("GET", endpoint, installation_id)

        if response.status_code != 200:
            return []

        data = response.json()
        return [org["login"] for org in data]

    async def check_user_permission_level(
        self,
        repo_owner: str,
        repo_name: str,
        username: str,
        installation_id: int,
    ) -> str:
        """
        Check a user's permission level on a repository.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            username: GitHub username
            installation_id: Installation ID for auth

        Returns:
            Permission level string
        """
        endpoint = (
            f"/repos/{repo_owner}/{repo_name}/collaborators/{username}/permission"
        )
        response = await self._request("GET", endpoint, installation_id)

        if response.status_code != 200:
            return "none"

        data = response.json()
        return data.get("permission", "none")
