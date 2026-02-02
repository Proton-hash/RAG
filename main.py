"""
Main entry point and orchestrator for the RAG data ingestion pipeline.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from config import (
    ES_API_KEY,
    ES_HOST,
    ES_INDEX,
    ES_PASSWORD,
    ES_USERNAME,
    LOG_FORMAT,
    require_github_token,
)
from data_ingestion import GitHubAPIClient, fetch_all_commits, fetch_all_projects
from constants import DEFAULT_COMMITS_DIR, DEFAULT_PROJECTS_DIR, DEFAULT_PROCESSED_DIR
from data_processing.normalizer import normalize_projects_and_commits
from data_processing.indexer import index_normalized_projects


logger = logging.getLogger(__name__)


def run_pipeline(
    token: str,
    projects_dir: Path | str = DEFAULT_PROJECTS_DIR,
    commits_dir: Path | str = DEFAULT_COMMITS_DIR,
    skip_projects: bool = False,
    skip_commits: bool = False,
    skip_normalization: bool = False,
    skip_indexing: bool = False,
    es_host: str = "http://localhost:9200",
    es_username: str | None = None,
    es_password: str | None = None,
    es_api_key: str | None = None,
    es_index_name: str = "github_projects",
    recreate_index: bool = False,
) -> dict:
    """
    Orchestrate the full data ingestion pipeline.

    Runs in order: projects fetch → commits fetch → normalization → elasticsearch indexing.
    Commits fetcher reads from projects output, so projects must run first
    unless skip_projects is True (uses existing data).

    Args:
        token: GitHub personal access token.
        projects_dir: Directory for raw project JSON.
        commits_dir: Directory for raw commit JSON.
        skip_projects: If True, skip projects fetch (use existing data).
        skip_commits: If True, skip commits fetch.
        skip_normalization: If True, skip normalization step.
        skip_indexing: If True, skip Elasticsearch indexing.
        es_host: Elasticsearch host URL.
        es_username: Elasticsearch username (optional).
        es_password: Elasticsearch password (optional).
        es_api_key: Elasticsearch API key (optional, preferred).
        es_index_name: Name of the Elasticsearch index.
        recreate_index: If True, delete and recreate the index.

    Returns:
        Dict with pipeline results: projects_count, commits_by_repo, total_commits, normalized_count, es_stats.
    """
    client = GitHubAPIClient(token=token)
    result: dict = {
        "projects_count": 0,
        "commits_by_repo": {},
        "total_commits": 0,
        "normalized_count": 0,
        "es_indexed": 0,
        "es_errors": 0,
        "es_stats": {},
    }

    # Step 1: Fetch projects
    if not skip_projects:
        logger.info("Step 1: Fetching projects")
        projects = fetch_all_projects(client, output_dir=projects_dir)
        result["projects_count"] = len(projects)
        logger.info("Step 1 complete: %d projects saved to %s", len(projects), projects_dir)
    else:
        logger.info("Step 1: Skipping projects fetch (using existing data)")
        if not Path(projects_dir).exists():
            raise FileNotFoundError(
                f"Cannot skip projects: {projects_dir} does not exist. Run without --skip-projects first."
            )

    # Step 2: Fetch commits (depends on projects data)
    if not skip_commits:
        logger.info("Step 2: Fetching commits for all projects")
        commits_by_repo = fetch_all_commits(
            client,
            projects_dir=projects_dir,
            commits_dir=commits_dir,
        )
        result["commits_by_repo"] = commits_by_repo
        result["total_commits"] = sum(len(c) for c in commits_by_repo.values())
        logger.info(
            "Step 2 complete: %d total commits across %d repos, saved to %s",
            result["total_commits"],
            len(commits_by_repo),
            commits_dir,
        )
    else:
        logger.info("Step 2: Skipping commits fetch")

    # Step 3: Normalize and combine projects with commits
    normalized_file = DEFAULT_PROCESSED_DIR / "normalized_projects.json"
    if not skip_normalization:
        logger.info("Step 3: Normalizing projects and commits data")
        normalized_projects = normalize_projects_and_commits(
            projects_dir=projects_dir,
            commits_dir=commits_dir,
        )
        result["normalized_count"] = len(normalized_projects)
        
        DEFAULT_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(normalized_file, "w", encoding="utf-8") as f:
            json.dump(normalized_projects, f, ensure_ascii=False, indent=2)
        
        logger.info(
            "Step 3 complete: %d normalized projects saved to %s",
            len(normalized_projects),
            normalized_file,
        )
    else:
        logger.info("Step 3: Skipping normalization")
        if not normalized_file.exists():
            raise FileNotFoundError(
                f"Cannot skip normalization: {normalized_file} does not exist. Run without --skip-normalization first."
            )

    # Step 4: Index into Elasticsearch
    if not skip_indexing:
        logger.info("Step 4: Indexing projects into Elasticsearch")
        try:
            es_result = index_normalized_projects(
                es_host=es_host,
                es_username=es_username,
                es_password=es_password,
                es_api_key=es_api_key,
                index_name=es_index_name,
                input_file=normalized_file,
                recreate_index=recreate_index,
            )
            result["es_indexed"] = es_result["indexed_projects"]
            result["es_errors"] = es_result["errors"]
            result["es_stats"] = es_result["statistics"]
            logger.info(
                "Step 4 complete: %d projects indexed into '%s', %d errors",
                result["es_indexed"],
                es_index_name,
                result["es_errors"],
            )
        except Exception as e:
            logger.error(f"Elasticsearch indexing failed: {e}")
            logger.warning("Pipeline will continue, but Elasticsearch indexing was not completed")
    else:
        logger.info("Step 4: Skipping Elasticsearch indexing")

    return result


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="RAG data ingestion pipeline: fetch GitHub projects and commits, then index into Elasticsearch.",
    )
    parser.add_argument(
        "--skip-projects",
        action="store_true",
        help="Skip projects fetch; use existing data in data/raw/projects",
    )
    parser.add_argument(
        "--skip-commits",
        action="store_true",
        help="Skip commits fetch",
    )
    parser.add_argument(
        "--skip-normalization",
        action="store_true",
        help="Skip normalization step",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Skip Elasticsearch indexing",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=DEFAULT_PROJECTS_DIR,
        help=f"Directory for raw project JSON (default: {DEFAULT_PROJECTS_DIR})",
    )
    parser.add_argument(
        "--commits-dir",
        type=Path,
        default=DEFAULT_COMMITS_DIR,
        help=f"Directory for raw commit JSON (default: {DEFAULT_COMMITS_DIR})",
    )
    parser.add_argument(
        "--es-host",
        type=str,
        default=ES_HOST,
        help="Elasticsearch host URL",
    )
    parser.add_argument(
        "--es-username",
        type=str,
        help="Elasticsearch username (optional)",
    )
    parser.add_argument(
        "--es-password",
        type=str,
        help="Elasticsearch password (optional)",
    )
    parser.add_argument(
        "--es-api-key",
        type=str,
        help="Elasticsearch API key (optional, preferred over username/password)",
    )
    parser.add_argument(
        "--es-index",
        type=str,
        default=ES_INDEX,
        help="Elasticsearch index name",
    )
    parser.add_argument(
        "--recreate-index",
        action="store_true",
        help="Delete and recreate Elasticsearch index if it exists",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    if LOG_FORMAT == "json":
        logging.root.handlers.clear()
        handler = logging.StreamHandler()

        class JsonFormatter(logging.Formatter):
            def format(self, record):
                return json.dumps({
                    "time": self.formatTime(record),
                    "level": record.levelname,
                    "name": record.name,
                    "message": record.getMessage(),
                }, default=str)

        handler.setFormatter(JsonFormatter())
        logging.root.addHandler(handler)
    else:
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    logging.root.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    try:
        token = require_github_token()
    except ValueError as e:
        logger.error("%s", e)
        return 1

    es_username = args.es_username or ES_USERNAME
    es_password = args.es_password or ES_PASSWORD
    es_api_key = args.es_api_key or ES_API_KEY

    try:
        result = run_pipeline(
            token=token,
            projects_dir=args.projects_dir,
            commits_dir=args.commits_dir,
            skip_projects=args.skip_projects,
            skip_commits=args.skip_commits,
            skip_normalization=args.skip_normalization,
            skip_indexing=args.skip_indexing,
            es_host=args.es_host,
            es_username=es_username,
            es_password=es_password,
            es_api_key=es_api_key,
            es_index_name=args.es_index,
            recreate_index=args.recreate_index,
        )
        print("\nPipeline Complete")
        print(f"  Projects: {result['projects_count']} | Commits: {result['total_commits']} | Normalized: {result['normalized_count']}")
        if result["es_indexed"] > 0:
            print(f"  ES: {result['es_indexed']} indexed, {result['es_errors']} errors")
        return 0
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())