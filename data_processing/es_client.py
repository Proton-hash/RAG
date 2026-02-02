"""
Elasticsearch client wrapper for managing connections and operations.
"""

import logging
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """
    Wrapper for Elasticsearch Python client with helper methods.
    """

    def __init__(
        self,
        hosts: List[str] | str = "http://localhost:9200",
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        verify_certs: bool = True,
        **kwargs,
    ):
        """
        Initialize Elasticsearch client.

        Args:
            hosts: Elasticsearch host(s). Can be a single URL or list of URLs.
            username: Basic auth username (optional).
            password: Basic auth password (optional).
            api_key: API key for authentication (optional, preferred over basic auth).
            verify_certs: Whether to verify SSL certificates.
            **kwargs: Additional arguments to pass to Elasticsearch client.
        """
        if isinstance(hosts, str):
            hosts = [hosts]

        # Build authentication
        auth_kwargs = {}
        if api_key:
            auth_kwargs["api_key"] = api_key
        elif username and password:
            auth_kwargs["basic_auth"] = (username, password)

        self.client = Elasticsearch(
            hosts=hosts,
            verify_certs=verify_certs,
            **auth_kwargs,
            **kwargs,
        )

        # Test connection
        if self.client.ping():
            logger.info("Successfully connected to Elasticsearch")
            info = self.client.info()
            logger.info(f"Elasticsearch version: {info['version']['number']}")
        else:
            raise ConnectionError("Failed to connect to Elasticsearch")

    def create_index(
        self,
        index_name: str,
        mappings: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        delete_if_exists: bool = False,
    ) -> bool:
        """
        Create an index with optional mappings and settings.

        Args:
            index_name: Name of the index to create.
            mappings: Index mappings (field types, etc.).
            settings: Index settings (shards, replicas, analyzers, etc.).
            delete_if_exists: If True, delete existing index before creating.

        Returns:
            True if index was created, False if it already exists.
        """
        if delete_if_exists and self.client.indices.exists(index=index_name):
            logger.warning(f"Deleting existing index: {index_name}")
            self.client.indices.delete(index=index_name)

        if self.client.indices.exists(index=index_name):
            logger.info(f"Index '{index_name}' already exists")
            return False

        body = {}
        if mappings:
            body["mappings"] = mappings
        if settings:
            body["settings"] = settings

        self.client.indices.create(index=index_name, body=body)
        logger.info(f"Created index: {index_name}")
        return True

    def delete_index(self, index_name: str) -> bool:
        """
        Delete an index.

        Args:
            index_name: Name of the index to delete.

        Returns:
            True if deleted, False if index doesn't exist.
        """
        if not self.client.indices.exists(index=index_name):
            logger.warning(f"Index '{index_name}' does not exist")
            return False

        self.client.indices.delete(index=index_name)
        logger.info(f"Deleted index: {index_name}")
        return True

    def index_document(
        self,
        index_name: str,
        document: Dict[str, Any],
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Index a single document.

        Args:
            index_name: Name of the index.
            document: Document to index.
            doc_id: Optional document ID. If not provided, ES generates one.

        Returns:
            Response from Elasticsearch.
        """
        response = self.client.index(
            index=index_name,
            id=doc_id,
            document=document,
        )
        return response

    def bulk_index(
        self,
        index_name: str,
        documents: List[Dict[str, Any]],
        id_field: Optional[str] = None,
        chunk_size: int = 500,
    ) -> tuple[int, int]:
        """
        Bulk index multiple documents.

        Args:
            index_name: Name of the index.
            documents: List of documents to index.
            id_field: Field name to use as document ID (optional).
            chunk_size: Number of documents per bulk request.

        Returns:
            Tuple of (success_count, error_count).
        """
        actions = []
        for doc in documents:
            action = {
                "_index": index_name,
                "_source": doc,
            }
            if id_field and id_field in doc:
                action["_id"] = doc[id_field]

            actions.append(action)

        success, errors = bulk(
            self.client,
            actions,
            chunk_size=chunk_size,
            raise_on_error=False,
        )

        logger.info(f"Bulk indexed {success} documents, {len(errors)} errors")
        return success, len(errors)

    def search(
        self,
        index_name: str,
        query: Dict[str, Any],
        size: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Search documents in an index.

        Args:
            index_name: Name of the index.
            query: Elasticsearch query DSL.
            size: Number of results to return.
            **kwargs: Additional search parameters.

        Returns:
            Search response from Elasticsearch.
        """
        response = self.client.search(
            index=index_name,
            query=query,
            size=size,
            **kwargs,
        )
        return response

    def get_document(self, index_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID.

        Args:
            index_name: Name of the index.
            doc_id: Document ID.

        Returns:
            Document if found, None otherwise.
        """
        try:
            response = self.client.get(index=index_name, id=doc_id)
            return response["_source"]
        except Exception as e:
            logger.warning(f"Document not found: {doc_id} - {e}")
            return None

    def count_documents(self, index_name: str, query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents in an index.

        Args:
            index_name: Name of the index.
            query: Optional query to filter documents.

        Returns:
            Number of documents.
        """
        body = {"query": query} if query else None
        response = self.client.count(index=index_name, body=body)
        return response["count"]

    def refresh_index(self, index_name: str) -> None:
        """
        Refresh an index to make recent changes visible to search.

        Args:
            index_name: Name of the index.
        """
        self.client.indices.refresh(index=index_name)
        logger.info(f"Refreshed index: {index_name}")

    def close(self) -> None:
        """Close the Elasticsearch client connection."""
        self.client.close()
        logger.info("Elasticsearch client connection closed")