"""
Commits fetcher that uses the GitHub API client to fetch commits for all projects.
"""

import json
import logging
import re
from pathlib import Path

from constants import DEFAULT_COMMITS_DIR, DEFAULT_PROJECTS_DIR, PAGE_SIZE
from data_ingestion.github_client import GitHubAPIClient

logger = logging.getLogger(__name__)


def _safe_dir_name(owner: str, repo: str) -> str:
    """Create a filesystem-safe directory name from owner and repo."""
    safe = f"{owner}__{repo}"
    return re.sub(r'[<>:"/\\|?*]', "_", safe)


def _load_projects_from_dir(projects_dir: Path) -> list[dict]:
    """Load all projects from JSON files in the projects directory."""
    projects: list[dict] = []
    json_files = sorted(projects_dir.glob("*.json"))

    if not json_files:
        logger.warning("No JSON files found in %s", projects_dir)
        return projects

    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                projects.extend(data)
            else:
                logger.warning("Skipping %s: expected list, got %s", json_file, type(data))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load %s: %s", json_file, e, exc_info=True)
            raise

    return projects


def _extract_owner_repo(project: dict) -> tuple[str, str] | None:
    """Extract owner and repo from a project dict. Returns None if invalid."""
    try:
        name = project.get("name")
        owner_obj = project.get("owner")
        if not name or not owner_obj:
            return None
        login = owner_obj.get("login")
        if not login:
            return None
        return (login, name)
    except (TypeError, AttributeError):
        return None


def fetch_all_commits(
    client: GitHubAPIClient,
    projects_dir: Path | str = DEFAULT_PROJECTS_DIR,
    commits_dir: Path | str = DEFAULT_COMMITS_DIR,
    per_page: int = PAGE_SIZE,
) -> dict[str, list[dict]]:
    """
    Fetch commits for all projects loaded from the projects directory.

    Projects are read from JSON files in data/raw/projects. Each project dict
    must have "name" (repo) and "owner" with "login" (owner) keys.

    Args:
        client: Configured GitHubAPIClient instance.
        projects_dir: Directory containing project JSON files.
        commits_dir: Directory to save raw commit JSON files.
        per_page: Number of commits per page (default: 100, max: 100).

    Returns:
        Dict mapping "owner/repo" to list of commit dictionaries.
    """
    projects_path = Path(projects_dir)
    commits_path = Path(commits_dir)

    if not projects_path.exists():
        logger.error("Projects directory does not exist: %s", projects_path)
        raise FileNotFoundError(f"Projects directory not found: {projects_path}")

    projects = _load_projects_from_dir(projects_path)
    logger.info("Loaded %d projects from %s", len(projects), projects_path)

    # Deduplicate by owner/repo (same repo may appear in multiple page files)
    seen: set[tuple[str, str]] = set()
    unique_repos: list[tuple[str, str]] = []
    for project in projects:
        owner_repo = _extract_owner_repo(project)
        if owner_repo and owner_repo not in seen:
            seen.add(owner_repo)
            unique_repos.append(owner_repo)

    logger.info("Fetching commits for %d unique repos", len(unique_repos))

    result: dict[str, list[dict]] = {}

    for owner, repo in unique_repos:
        repo_key = f"{owner}/{repo}"
        endpoint = f"/repos/{owner}/{repo}/commits"
        repo_commits: list[dict] = []
        page = 1

        # Create output dir for this repo
        repo_dir = commits_path / _safe_dir_name(owner, repo)
        repo_dir.mkdir(parents=True, exist_ok=True)

        try:
            while True:
                logger.info("Fetching commits for %s (page %d)", repo_key, page)
                commits = client.get(
                    endpoint,
                    params={"per_page": per_page, "page": page},
                )

                if not isinstance(commits, list):
                    logger.error("Unexpected response type for %s: %s", repo_key, type(commits))
                    raise ValueError(f"Expected list, got {type(commits)}")

                if not commits:
                    logger.info("No more commits for %s", repo_key)
                    break

                # Save raw JSON for this page
                page_file = repo_dir / f"page_{page}.json"
                with open(page_file, "w") as f:
                    json.dump(commits, f, indent=2)
                logger.info("Saved %d commits to %s", len(commits), page_file)

                repo_commits.extend(commits)

                if len(commits) < per_page:
                    break

                page += 1

            result[repo_key] = repo_commits
            logger.info("Fetched %d commits for %s", len(repo_commits), repo_key)

        except Exception:
            logger.exception("Error fetching commits for %s", repo_key)
            raise

    total = sum(len(commits) for commits in result.values())
    logger.info("Fetched %d total commits across %d repos", total, len(result))
    return result
