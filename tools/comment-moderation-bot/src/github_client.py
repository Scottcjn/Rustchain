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

    @staticmethod
    def _json_object(data: Any, context: str) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError(f"{context} response must be a JSON object")
        return data

    @staticmethod
    def _json_list(data: Any, context: str) -> list[Any]:
        if not isinstance(data, list):
            raise ValueError(f"{context} response must be a JSON array")
        return data

    @staticmethod
    def _required_str(data: dict[str, Any], field: str, context: str) -> str:
        value = data.get(field)
        if not isinstance(value, str):
            raise ValueError(f"{context} response field {field!r} must be a string")
        return value

    @staticmethod
    def _required_int(data: dict[str, Any], field: str, context: str) -> int:
        value = data.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{context} response field {field!r} must be an integer")
        return value

    @classmethod
    def _parse_comment(cls, data: Any, context: str) -> CommentData:
        obj = cls._json_object(data, context)
        user = cls._json_object(obj.get("user"), context)
        body = obj.get("body")
        if body is None:
            body = ""
        elif not isinstance(body, str):
            raise ValueError(f"{context} response field 'body' must be a string or null")

        return CommentData(
            id=cls._required_int(obj, "id", context),
            body=body,
            author_login=cls._required_str(user, "login", context),
            author_association=cls._required_str(obj, "author_association", context),
            created_at=cls._required_str(obj, "created_at", context),
            updated_at=cls._required_str(obj, "updated_at", context),
            issue_url=cls._required_str(obj, "issue_url", context),
            html_url=cls._required_str(obj, "html_url", context),
        )

    @classmethod
    def _parse_issue(cls, data: Any, context: str) -> IssueData:
        obj = cls._json_object(data, context)
        labels = cls._json_list(obj.get("labels", []), context)
        label_names = []
        for label in labels:
            label_obj = cls._json_object(label, context)
            label_names.append(cls._required_str(label_obj, "name", context))

        comments_count = obj.get("comments", 0)
        if not isinstance(comments_count, int) or isinstance(comments_count, bool):
            raise ValueError(f"{context} response field 'comments' must be an integer")

        return IssueData(
            number=cls._required_int(obj, "number", context),
            title=cls._required_str(obj, "title", context),
            state=cls._required_str(obj, "state", context),
            labels=label_names,
            created_at=cls._required_str(obj, "created_at", context),
            comments_count=comments_count,
        )

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

        return self._parse_comment(data, "GitHub comment")

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

        return self._parse_issue(data, "GitHub issue")

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
            page_data = self._json_list(response.json(), "GitHub issue comments")

            if not page_data:
                break

            for data in page_data:
                comments.append(self._parse_comment(data, "GitHub issue comment"))

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

        data = self._json_list(response.json(), "GitHub user organizations")
        return [
            self._required_str(
                self._json_object(org, "GitHub user organization"),
                "login",
                "GitHub user organization",
            )
            for org in data
        ]

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

        data = self._json_object(response.json(), "GitHub permission")
        return data.get("permission", "none")
