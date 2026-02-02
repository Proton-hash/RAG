"""
Data processing module for normalizing and transforming raw GitHub data.
"""

from data_processing.normalizer import normalize_projects_and_commits
from data_processing.es_client import ElasticsearchClient
from data_processing.indexer import ProjectIndexer, index_normalized_projects

__all__ = [
    "normalize_projects_and_commits",
    "ElasticsearchClient",
    "ProjectIndexer",
    "index_normalized_projects",
]