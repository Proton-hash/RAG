import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_jsons_from_dir(directory: Path) -> list:
    """Load and flatten all lists from JSON files in a directory."""
    result = []
    for json_file in sorted(directory.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                result.extend(data) if isinstance(data, list) else result.append(data)
        except Exception as e:
            logger.warning("Skipping %s: %s", json_file, e)
    return result


def normalize_projects_and_commits(
    projects_dir: Path | str = "data/raw/projects",
    commits_dir: Path | str = "data/raw/commits",
) -> list:
    """Combine projects with their commits from raw JSON files."""
    projects_dir = Path(projects_dir)
    commits_dir = Path(commits_dir)
    projects_list = _load_jsons_from_dir(projects_dir)

    for project in projects_list:
        name = project.get("name")
        owner = project.get("owner", {})
        login = owner.get("login")
        if not name or not login:
            continue
        folder_name = f"{login}__{name}"
        commit_folder = commits_dir / folder_name
        project["commits"] = _load_jsons_from_dir(commit_folder) if commit_folder.exists() and commit_folder.is_dir() else []

    return projects_list
