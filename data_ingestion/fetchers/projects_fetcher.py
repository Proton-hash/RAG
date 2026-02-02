"""
Projects fetcher that uses the GitHub API client to fetch all repositories.
"""

import json
import logging
from pathlib import Path

from constants import DEFAULT_PROJECTS_DIR, PAGE_SIZE
from data_ingestion.github_client import GitHubAPIClient

logger = logging.getLogger(__name__)


def fetch_all_projects(
    client: GitHubAPIClient,
    output_dir: Path | str = DEFAULT_PROJECTS_DIR,
    per_page: int = PAGE_SIZE,
) -> list[dict]:
    """
    Fetch all projects (repositories) for the authenticated user.

    Uses pagination with 100 items per page, saves raw JSON to disk,
    and returns the combined list of project dictionaries.

    Args:
        client: Configured GitHubAPIClient instance.
        output_dir: Directory to save raw JSON files (default: data/raw/projects).
        per_page: Number of items per page (default: 100, max: 100).

    Returns:
        List of project (repository) dictionaries.

    Raises:
        requests.RequestException: If API requests fail after retries.
        OSError: If writing to disk fails.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    logger.info("Fetching projects, saving to %s", output_path.resolve())

    all_projects: list[dict] = []
    page = 1

    while True:
        logger.info("Fetching page %d (per_page=%d)", page, per_page)
        projects = client.get(
            "/user/repos",
            params={"per_page": per_page, "page": page},
        )

        if not isinstance(projects, list):
            logger.error("Unexpected response type: %s", type(projects))
            raise ValueError(f"Expected list, got {type(projects)}")

        if not projects:
            logger.info("Page %d empty, pagination complete", page)
            break

        # Save raw JSON for this page
        page_file = output_path / f"page_{page}.json"
        with open(page_file, "w") as f:
            json.dump(projects, f, indent=2)
        logger.info("Saved %d projects to %s", len(projects), page_file)

        all_projects.extend(projects)

        if len(projects) < per_page:
            logger.info(
                "Page %d has %d items (< %d), pagination complete",
                page,
                len(projects),
                per_page,
            )
            break

        page += 1

    logger.info("Fetched %d total projects across %d page(s)", len(all_projects), page)
    return all_projects
