"""GitLab REST API helpers using httpx."""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

_TIMEOUT = 30.0


class GitLabAPI:
    """Thin wrapper around GitLab REST v4 API."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=f"{self._base}/api/v4",
            headers={"PRIVATE-TOKEN": token} if not token.startswith("glpat-") and token else {"PRIVATE-TOKEN": token},
            timeout=_TIMEOUT,
        )
        # CI_JOB_TOKEN uses Job-Token header instead
        if token and not token.startswith("glpat-"):
            self._client.headers["JOB-TOKEN"] = token
            self._client.headers.pop("PRIVATE-TOKEN", None)

    def _get(self, path: str, **params: Any) -> Any:
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        resp = self._client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, json: dict[str, Any] | None = None) -> Any:
        resp = self._client.put(path, json=json)
        resp.raise_for_status()
        return resp.json()

    # ---- Project ----

    def get_project(self, project_id: int) -> dict[str, Any]:
        return self._get(f"/projects/{project_id}")

    # ---- Branches ----

    def create_branch(self, project_id: int, branch: str, ref: str = "main") -> dict[str, Any]:
        log.info("Creating branch %s from %s", branch, ref)
        return self._post(
            f"/projects/{project_id}/repository/branches",
            json={"branch": branch, "ref": ref},
        )

    def branch_exists(self, project_id: int, branch: str) -> bool:
        try:
            self._get(f"/projects/{project_id}/repository/branches/{branch}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    # ---- Commits ----

    def create_commit(
        self,
        project_id: int,
        branch: str,
        message: str,
        actions: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Create a commit via the Commits API.

        Each action: {"action": "create|update", "file_path": "...", "content": "..."}
        """
        log.info("Creating commit on %s with %d file actions", branch, len(actions))
        return self._post(
            f"/projects/{project_id}/repository/commits",
            json={
                "branch": branch,
                "commit_message": message,
                "actions": actions,
            },
        )

    # ---- Merge Requests ----

    def create_merge_request(
        self,
        project_id: int,
        source_branch: str,
        target_branch: str = "main",
        title: str = "",
        description: str = "",
        draft: bool = False,
        labels: str = "",
    ) -> dict[str, Any]:
        mr_title = f"Draft: {title}" if draft else title
        log.info("Creating MR: %s (%s → %s)", mr_title, source_branch, target_branch)
        return self._post(
            f"/projects/{project_id}/merge_requests",
            json={
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": mr_title,
                "description": description,
                "labels": labels,
            },
        )

    # ---- Issue comments ----

    def post_issue_comment(
        self, project_id: int, issue_iid: int, body: str
    ) -> dict[str, Any]:
        log.info("Posting comment on issue #%d", issue_iid)
        return self._post(
            f"/projects/{project_id}/issues/{issue_iid}/notes",
            json={"body": body},
        )

    # ---- File uploads (for .rpack artifact) ----

    def upload_file(self, project_id: int, file_path: str) -> dict[str, Any]:
        """Upload a file to the project and return the URL."""
        log.info("Uploading file %s", file_path)
        with open(file_path, "rb") as f:
            resp = self._client.post(
                f"/projects/{project_id}/uploads",
                files={"file": f},
            )
        resp.raise_for_status()
        return resp.json()
