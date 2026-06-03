from unittest.mock import AsyncMock, MagicMock

import pytest

from src.github_client import GitHubClient


@pytest.fixture
def client() -> GitHubClient:
    auth = MagicMock()
    auth.get_auth_headers = AsyncMock(return_value={"Authorization": "Bearer token"})
    return GitHubClient(auth=auth)


def make_response(payload, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


def comment_payload(**overrides):
    payload = {
        "id": 123,
        "body": "Looks suspicious",
        "user": {"login": "octocat"},
        "author_association": "NONE",
        "created_at": "2026-05-20T12:00:00Z",
        "updated_at": "2026-05-20T12:00:00Z",
        "issue_url": "https://api.github.com/repos/acme/demo/issues/1",
        "html_url": "https://github.com/acme/demo/issues/1#issuecomment-123",
    }
    payload.update(overrides)
    return payload


def issue_payload(**overrides):
    payload = {
        "number": 1,
        "title": "Issue title",
        "state": "open",
        "labels": [{"name": "triage"}],
        "created_at": "2026-05-20T12:00:00Z",
        "comments": 2,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_get_comment_validates_json_object(client: GitHubClient) -> None:
    client._request = AsyncMock(return_value=make_response([comment_payload()]))

    with pytest.raises(ValueError, match="GitHub comment response must be a JSON object"):
        await client.get_comment("acme", "demo", 123, 456)


@pytest.mark.asyncio
async def test_get_comment_validates_user_shape(client: GitHubClient) -> None:
    client._request = AsyncMock(
        return_value=make_response(comment_payload(user={"name": "Octo Cat"}))
    )

    with pytest.raises(ValueError, match="'login' must be a string"):
        await client.get_comment("acme", "demo", 123, 456)


@pytest.mark.asyncio
async def test_get_comment_allows_null_body(client: GitHubClient) -> None:
    client._request = AsyncMock(return_value=make_response(comment_payload(body=None)))

    comment = await client.get_comment("acme", "demo", 123, 456)

    assert comment.body == ""
    assert comment.author_login == "octocat"


@pytest.mark.asyncio
async def test_get_issue_validates_labels_array(client: GitHubClient) -> None:
    client._request = AsyncMock(return_value=make_response(issue_payload(labels={})))

    with pytest.raises(ValueError, match="GitHub issue response must be a JSON array"):
        await client.get_issue("acme", "demo", 1, 456)


@pytest.mark.asyncio
async def test_get_issue_comments_validates_page_array(client: GitHubClient) -> None:
    client._request = AsyncMock(return_value=make_response({"items": [comment_payload()]}))

    with pytest.raises(
        ValueError, match="GitHub issue comments response must be a JSON array"
    ):
        await client.get_issue_comments("acme", "demo", 1, 456)


@pytest.mark.asyncio
async def test_get_issue_comments_validates_each_comment(client: GitHubClient) -> None:
    client._request = AsyncMock(return_value=make_response([comment_payload(user=None)]))

    with pytest.raises(
        ValueError, match="GitHub issue comment response must be a JSON object"
    ):
        await client.get_issue_comments("acme", "demo", 1, 456)


@pytest.mark.asyncio
async def test_get_user_orgs_validates_json_array(client: GitHubClient) -> None:
    client._request = AsyncMock(return_value=make_response({"login": "not-an-array"}))

    with pytest.raises(
        ValueError, match="GitHub user organizations response must be a JSON array"
    ):
        await client.get_user_orgs("octocat", 456)
