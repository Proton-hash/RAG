"""Data ingestion package for GitHub API clients and fetchers."""

from data_ingestion.github_client import GitHubAPIClient
from data_ingestion.fetchers.commits_fetcher import fetch_all_commits
from data_ingestion.fetchers.projects_fetcher import fetch_all_projects

__all__ = [
    "GitHubAPIClient",
    "fetch_all_projects",
    "fetch_all_commits",
]
