"""Fetchers for GitHub API data."""

from data_ingestion.fetchers.commits_fetcher import fetch_all_commits
from data_ingestion.fetchers.projects_fetcher import fetch_all_projects

__all__ = [
    "fetch_all_projects",
    "fetch_all_commits",
]
