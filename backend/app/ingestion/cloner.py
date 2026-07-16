"""
CodeLens — Cloner (app/ingestion/cloner.py)

Clones GitHub repositories to local disk for indexing.
Replaces: app/services/github_service.py
"""

import os
import re
import shutil
import stat
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Optional

from git import Repo, GitCommandError

from app.config import get_settings
from app.utils.logger import get_logger


def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)


logger = get_logger(__name__)
settings = get_settings()


def parse_repo_url(url: str) -> dict:
    """
    Parse a GitHub URL into owner and repo name.

    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo.git
    """
    patterns = [
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
    ]

    for pattern in patterns:
        match = re.match(pattern, url.strip())
        if match:
            owner, repo = match.groups()
            return {
                "owner": owner,
                "repo": repo,
                "repo_id": f"{owner}/{repo}",
                "clone_url": f"https://github.com/{owner}/{repo}.git",
            }

    raise ValueError(f"Invalid GitHub URL: {url}")


def check_repo_size(owner: str, repo: str) -> None:
    """
    Use the GitHub API to check repository size before cloning.
    Raises ValueError if the repo exceeds settings.max_repo_size_mb.

    Works for public repos without a token (lower rate limit).
    Warns and proceeds if the API call fails (network issue, rate limit).
    """
    max_bytes = settings.max_repo_size_mb * 1024  # GitHub API size is in KB
    api_url   = f"https://api.github.com/repos/{owner}/{repo}"

    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    try:
        req  = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data      = json.loads(resp.read())
            size_kb   = data.get("size", 0)   # size in KB
            size_mb   = round(size_kb / 1024, 1)

        logger.info(
            "clone_size_check",
            repo=f"{owner}/{repo}",
            size_mb=size_mb,
            limit_mb=settings.max_repo_size_mb,
        )

        if size_kb > max_bytes:
            raise ValueError(
                f"Repository {owner}/{repo} is {size_mb} MB, which exceeds the "
                f"{settings.max_repo_size_mb} MB limit. "
                f"Increase MAX_REPO_SIZE_MB in .env to index larger repositories."
            )

    except ValueError:
        raise   # re-raise our own size error
    except Exception as exc:
        # Network error, rate limit, private repo without token — warn and proceed
        logger.warning(
            "clone_size_check_failed",
            repo=f"{owner}/{repo}",
            error=str(exc),
            note="Proceeding without size check.",
        )


def clone_repository(
    repo_url: str,
    branch: Optional[str] = None,
) -> Path:
    """
    Clone a GitHub repository to local storage (shallow, single-branch).

    Args:
        repo_url: GitHub repository URL.
        branch: Specific branch to clone (optional).

    Returns:
        Path to the cloned repository.
    """
    repo_info = parse_repo_url(repo_url)
    clone_dir = Path(settings.repos_dir) / repo_info["owner"] / repo_info["repo"]

    if clone_dir.exists():
        logger.info(
            "clone_removing_old_dir",
            path=str(clone_dir),
        )
        shutil.rmtree(clone_dir, onerror=remove_readonly)

    clone_dir.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "clone_started",
        repo_id=repo_info["repo_id"],
        branch=branch or "default",
        target=str(clone_dir),
    )

    # Guard: check repo size before allocating disk space
    check_repo_size(repo_info["owner"], repo_info["repo"])

    try:
        clone_kwargs: dict = {
            "depth": 1,
            "single_branch": True,
        }
        if branch:
            clone_kwargs["branch"] = branch

        clone_url = repo_info["clone_url"]
        if settings.github_token:
            clone_url = clone_url.replace(
                "https://github.com",
                f"https://{settings.github_token}@github.com",
            )

        Repo.clone_from(
            clone_url,
            str(clone_dir),
            env={"GIT_CLONE_PROTECTION_ACTIVE": "false", "GIT_TERMINAL_PROMPT": "0"},
            **clone_kwargs,
        )

        logger.info(
            "clone_successful",
            repo_id=repo_info["repo_id"],
            path=str(clone_dir),
        )
        return clone_dir

    except GitCommandError as e:
        logger.error(
            "clone_failed",
            repo_id=repo_info["repo_id"],
            error=str(e),
        )
        raise RuntimeError(f"Failed to clone repository: {e}")


def cleanup_repository(repo_path: Path) -> None:
    """Remove a cloned repository from disk."""
    if repo_path.exists():
        shutil.rmtree(repo_path, onerror=remove_readonly)
        logger.info("clone_removed", path=str(repo_path))
