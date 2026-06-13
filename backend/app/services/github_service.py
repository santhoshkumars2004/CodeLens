"""
StackSense GitHub Service.

Handles cloning GitHub repositories and extracting metadata.
"""

import os
import re
import shutil
import stat
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

    Supports formats:
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


def clone_repository(
    repo_url: str,
    branch: Optional[str] = None,
) -> Path:
    """
    Clone a GitHub repository to local storage.

    Args:
        repo_url: GitHub repository URL.
        branch: Specific branch to clone (optional).

    Returns:
        Path to the cloned repository.
    """
    repo_info = parse_repo_url(repo_url)
    clone_dir = Path(settings.repos_dir) / repo_info["owner"] / repo_info["repo"]

    # Remove existing clone if present
    if clone_dir.exists():
        logger.info("removing_existing_clone", path=str(clone_dir))
        shutil.rmtree(clone_dir, onerror=remove_readonly)

    clone_dir.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "cloning_repository",
        repo_id=repo_info["repo_id"],
        branch=branch or "default",
        target=str(clone_dir),
    )

    try:
        clone_kwargs = {
            "depth": 1,  # Shallow clone for speed
            "single_branch": True,
        }

        if branch:
            clone_kwargs["branch"] = branch

        # Use GitHub token if available for private repos
        clone_url = repo_info["clone_url"]
        if settings.github_token:
            clone_url = clone_url.replace(
                "https://github.com",
                f"https://{settings.github_token}@github.com",
            )

        Repo.clone_from(clone_url, str(clone_dir), **clone_kwargs)

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
        logger.info("repository_cleaned_up", path=str(repo_path))
