"""
Indexer for ingesting normalized GitHub projects and commits into Elasticsearch.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_processing.es_client import ElasticsearchClient

logger = logging.getLogger(__name__)


# Index settings
PROJECTS_INDEX_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 1,
    "analysis": {
        "analyzer": {
            "code_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "stop"],
            }
        }
    },
}


class ProjectIndexer:
    """
    Indexer for GitHub projects with commits.
    """

    def __init__(
        self,
        es_client: ElasticsearchClient,
        index_name: str = "github_projects",
    ):
        """
        Initialize the indexer.

        Args:
            es_client: Elasticsearch client instance.
            index_name: Name of the index to create/use.
        """
        self.es_client = es_client
        self.index_name = index_name

    def create_index(self, delete_if_exists: bool = False) -> bool:
        """
        Create the projects index with mappings and settings.

        Args:
            delete_if_exists: If True, delete existing index before creating.

        Returns:
            True if index was created, False if it already exists.
        """
        return self.es_client.create_index(
            index_name=self.index_name,
            mappings=PROJECTS_INDEX_MAPPINGS,
            settings=PROJECTS_INDEX_SETTINGS,
            delete_if_exists=delete_if_exists,
        )

    def index_projects(
        self,
        projects: List[Dict[str, Any]],
        chunk_size: int = 500,
    ) -> tuple[int, int]:
        """
        Index a list of projects.

        Args:
            projects: List of normalized project dictionaries.
            chunk_size: Number of documents per bulk request.

        Returns:
            Tuple of (success_count, error_count).
        """
        if not projects:
            logger.warning("No projects to index")
            return 0, 0

        logger.info(f"Indexing {len(projects)} projects into '{self.index_name}'")

        success, errors = self.es_client.bulk_index(
            index_name=self.index_name,
            documents=projects,
            id_field="id",
            chunk_size=chunk_size,
        )

        # Refresh index to make documents searchable
        self.es_client.refresh_index(self.index_name)

        return success, errors

    def index_from_file(
        self,
        file_path: Path | str,
        chunk_size: int = 500,
    ) -> tuple[int, int]:
        """
        Load and index projects from a JSON file.

        Args:
            file_path: Path to normalized_projects.json file.
            chunk_size: Number of documents per bulk request.

        Returns:
            Tuple of (success_count, error_count).
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Loading projects from {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            projects = json.load(f)

        if not isinstance(projects, list):
            raise ValueError("Expected a list of projects in the JSON file")

        return self.index_projects(projects, chunk_size=chunk_size)

    def search_projects(
        self,
        query_string: Optional[str] = None,
        language: Optional[str] = None,
        min_stars: Optional[int] = None,
        size: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for projects with optional filters.

        Args:
            query_string: Text to search in name/description.
            language: Filter by programming language.
            min_stars: Minimum number of stars.
            size: Number of results to return.

        Returns:
            List of matching projects.
        """
        must_conditions = []

        if query_string:
            must_conditions.append({
                "multi_match": {
                    "query": query_string,
                    "fields": ["name^2", "description", "full_name"],
                }
            })

        if language:
            must_conditions.append({"term": {"language": language}})

        if min_stars is not None:
            must_conditions.append({
                "range": {"stargazers_count": {"gte": min_stars}}
            })

        query = {
            "bool": {
                "must": must_conditions if must_conditions else [{"match_all": {}}]
            }
        }

        response = self.es_client.search(
            index_name=self.index_name,
            query=query,
            size=size,
        )

        return [hit["_source"] for hit in response["hits"]["hits"]]

    def search_by_commit_message(
        self,
        message: str,
        size: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search projects by commit message content.

        Args:
            message: Text to search in commit messages.
            size: Number of results to return.

        Returns:
            List of matching projects.
        """
        query = {
            "nested": {
                "path": "commits",
                "query": {
                    "match": {
                        "commits.commit.message": message
                    }
                },
            }
        }

        response = self.es_client.search(
            index_name=self.index_name,
            query=query,
            size=size,
        )

        return [hit["_source"] for hit in response["hits"]["hits"]]

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the indexed projects.

        Returns:
            Dictionary with index statistics.
        """
        total_docs = self.es_client.count_documents(self.index_name)

        # Get aggregations for languages
        agg_query = {
            "match_all": {}
        }

        response = self.es_client.client.search(
            index=self.index_name,
            query=agg_query,
            size=0,
            aggs={
                "languages": {
                    "terms": {"field": "language", "size": 10}
                },
                "avg_stars": {
                    "avg": {"field": "stargazers_count"}
                },
                "total_commits": {
                    "nested": {"path": "commits"},
                    "aggs": {
                        "count": {"value_count": {"field": "commits.sha"}}
                    },
                },
            },
        )

        return {
            "total_projects": total_docs,
            "top_languages": [
                {"language": b["key"], "count": b["doc_count"]}
                for b in response["aggregations"]["languages"]["buckets"]
            ],
            "avg_stars": response["aggregations"]["avg_stars"]["value"],
            "total_commits": response["aggregations"]["total_commits"]["count"]["value"],
        }


def index_normalized_projects(
    es_host: str = "http://localhost:9200",
    es_username: Optional[str] = None,
    es_password: Optional[str] = None,
    es_api_key: Optional[str] = None,
    index_name: str = "github_projects",
    input_file: Path | str = "data/processed/normalized_projects.json",
    recreate_index: bool = False,
    chunk_size: int = 500,
) -> Dict[str, Any]:
    """
    Main function to index normalized projects into Elasticsearch.

    Args:
        es_host: Elasticsearch host URL.
        es_username: Elasticsearch username (optional).
        es_password: Elasticsearch password (optional).
        es_api_key: Elasticsearch API key (optional, preferred).
        index_name: Name of the index to create/use.
        input_file: Path to normalized_projects.json.
        recreate_index: If True, delete and recreate the index.
        chunk_size: Number of documents per bulk request.

    Returns:
        Dictionary with indexing results and statistics.
    """
    # Initialize Elasticsearch client
    es_client = ElasticsearchClient(
        hosts=es_host,
        username=es_username,
        password=es_password,
        api_key=es_api_key,
    )

    # Initialize indexer
    indexer = ProjectIndexer(es_client, index_name=index_name)

    # Create index
    indexer.create_index(delete_if_exists=recreate_index)

    # Index projects
    success, errors = indexer.index_from_file(input_file, chunk_size=chunk_size)

    # Get statistics
    stats = indexer.get_index_stats()

    result = {
        "indexed_projects": success,
        "errors": errors,
        "statistics": stats,
    }

    logger.info(f"Indexing complete: {success} projects indexed, {errors} errors")
    logger.info(f"Statistics: {stats}")

    return result