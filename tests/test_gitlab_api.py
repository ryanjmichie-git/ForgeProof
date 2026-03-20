"""Tests for GitLab API client."""

from unittest.mock import MagicMock, patch

import httpx

from forgeproof.gitlab.api import GitLabAPI


@patch("forgeproof.gitlab.api.httpx.Client")
def test_init_pat_token(mock_client_cls):
    """PAT token uses PRIVATE-TOKEN header."""
    GitLabAPI("https://gitlab.com", "glpat-abc123")
    call_kwargs = mock_client_cls.call_args
    headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))
    assert headers.get("PRIVATE-TOKEN") == "glpat-abc123"


@patch("forgeproof.gitlab.api.httpx.Client")
def test_init_job_token(mock_client_cls):
    """CI job token uses JOB-TOKEN header."""
    GitLabAPI("https://gitlab.com", "ci-job-token-xyz")
    call_kwargs = mock_client_cls.call_args
    headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))
    assert headers.get("JOB-TOKEN") == "ci-job-token-xyz"


@patch("forgeproof.gitlab.api.httpx.Client")
def test_init_base_url_trailing_slash(mock_client_cls):
    """Trailing slash is stripped from base URL."""
    GitLabAPI("https://gitlab.com/", "glpat-test")
    call_kwargs = mock_client_cls.call_args
    base_url = call_kwargs.kwargs.get("base_url", call_kwargs[1].get("base_url", ""))
    assert not base_url.endswith("//")
    assert base_url == "https://gitlab.com/api/v4"


@patch("forgeproof.gitlab.api.httpx.Client")
def test_branch_exists_url_encoding(mock_client_cls):
    """Branch names with / are URL-encoded."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "forgeproof/42-fix"}
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    api = GitLabAPI("https://gitlab.com", "glpat-test")
    result = api.branch_exists(123, "forgeproof/42-fix")

    assert result is True
    get_call = mock_client.get.call_args
    path = get_call[0][0]
    # The branch name should be URL-encoded in the path
    assert "forgeproof%2F42-fix" in path


@patch("forgeproof.gitlab.api.httpx.Client")
def test_branch_exists_404(mock_client_cls):
    """branch_exists returns False for 404."""
    mock_client = MagicMock()
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)
    mock_client.get.side_effect = error
    mock_client_cls.return_value = mock_client

    api = GitLabAPI("https://gitlab.com", "glpat-test")
    assert api.branch_exists(123, "nonexistent") is False
