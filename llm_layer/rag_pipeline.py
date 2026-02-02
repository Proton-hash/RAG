"""
Complete RAG pipeline orchestrator.
Combines query generation, Elasticsearch search, and answer generation.
"""

import logging
from typing import Any, Dict, Optional

from data_processing import ElasticsearchClient
from llm_layer import QueryGenerator, AnswerGenerator

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    End-to-end RAG pipeline for GitHub repository Q&A.
    """

    def __init__(
        self,
        groq_api_key: str,
        es_host: str = "http://localhost:9200",
        es_username: Optional[str] = None,
        es_password: Optional[str] = None,
        es_api_key: Optional[str] = None,
        index_name: str = "github_projects",
        query_model: str = "llama-3.3-70b-versatile",
        answer_model: str = "llama-3.3-70b-versatile",
        query_temperature: float = 0.0,
        answer_temperature: float = 0.3,
    ):
        """
        Initialize the RAG pipeline.

        Args:
            groq_api_key: Groq API key.
            es_host: Elasticsearch host URL.
            es_username: Elasticsearch username (optional).
            es_password: Elasticsearch password (optional).
            es_api_key: Elasticsearch API key (optional).
            index_name: Name of the Elasticsearch index.
            query_model: Groq model for query generation.
            answer_model: Groq model for answer generation.
            query_temperature: Temperature for query generation.
            answer_temperature: Temperature for answer generation.
        """
        # Initialize Elasticsearch client
        self.es_client = ElasticsearchClient(
            hosts=es_host,
            username=es_username,
            password=es_password,
            api_key=es_api_key,
        )
        self.index_name = index_name

        # Initialize query generator
        self.query_generator = QueryGenerator(
            groq_api_key=groq_api_key,
            model_name=query_model,
            temperature=query_temperature,
        )

        # Initialize answer generator
        self.answer_generator = AnswerGenerator(
            groq_api_key=groq_api_key,
            model_name=answer_model,
            temperature=answer_temperature,
        )

        logger.info(f"RAG Pipeline initialized with index: {index_name}")

    def ask(
        self,
        question: str,
        max_results: int = 10,
        include_commits: bool = True,
        return_metadata: bool = False,
    ) -> str | Dict[str, Any]:
        """
        Ask a question and get an answer using the full RAG pipeline.

        Args:
            question: Natural language question.
            max_results: Maximum number of search results to retrieve.
            include_commits: Whether to include commit information.
            return_metadata: If True, return dict with answer and metadata.

        Returns:
            Answer string or dict with answer and metadata.
        """
        logger.info(f"Processing question: {question}")

        # Step 1: Generate Elasticsearch query
        try:
            es_query = self.query_generator.generate_query(
                question=question,
                es_client=self.es_client,
                index_name=self.index_name,
            )
            
            # Override size if specified
            if max_results:
                es_query["size"] = max_results
            
            logger.info(f"Generated ES query: {es_query}")
        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            return self._error_response(
                f"I had trouble understanding your question. Could you rephrase it?",
                return_metadata,
            )

        # Step 2: Search Elasticsearch
        try:
            search_results = self.es_client.search(
                index_name=self.index_name,
                query=es_query.get("query", {"match_all": {}}),
                size=es_query.get("size", max_results),
                sort=es_query.get("sort"),
            )
            logger.info(f"Found {search_results['hits']['total']['value']} results")
        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")
            return self._error_response(
                f"I encountered an error searching the database. Please try again.",
                return_metadata,
            )

        # Step 3: Generate answer
        try:
            if return_metadata:
                result = self.answer_generator.generate_answer_with_sources(
                    question=question,
                    search_results=search_results,
                    include_commits=include_commits,
                )
                result["query"] = es_query
                return result
            else:
                answer = self.answer_generator.generate_answer(
                    question=question,
                    search_results=search_results,
                    include_commits=include_commits,
                )
                return answer
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return self._error_response(
                f"I found some results but had trouble generating an answer.",
                return_metadata,
            )

    def search_only(self, question: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Generate query and search without generating answer.

        Args:
            question: Natural language question.
            max_results: Maximum results to return.

        Returns:
            Elasticsearch search results.
        """
        es_query = self.query_generator.generate_query(
            question=question,
            es_client=self.es_client,
            index_name=self.index_name,
        )
        
        if max_results:
            es_query["size"] = max_results

        return self.es_client.search(
            index_name=self.index_name,
            query=es_query.get("query", {"match_all": {}}),
            size=es_query.get("size", max_results),
            sort=es_query.get("sort"),
        )

    def answer_with_custom_query(
        self,
        question: str,
        es_query: Dict[str, Any],
        include_commits: bool = True,
    ) -> str:
        """
        Generate answer using a custom Elasticsearch query.

        Args:
            question: Original question (for context).
            es_query: Custom Elasticsearch query.
            include_commits: Whether to include commits.

        Returns:
            Generated answer.
        """
        search_results = self.es_client.search(
            index_name=self.index_name,
            query=es_query.get("query", {"match_all": {}}),
            size=es_query.get("size", 10),
            sort=es_query.get("sort"),
        )

        return self.answer_generator.generate_answer(
            question=question,
            search_results=search_results,
            include_commits=include_commits,
        )

    def get_project_summary(self, project_name: str) -> str:
        """
        Get a summary of a specific project.

        Args:
            project_name: Name of the project.

        Returns:
            Project summary.
        """
        # Search for the specific project
        es_query = {
            "query": {
                "term": {"name.keyword": project_name}
            },
            "size": 1
        }

        results = self.es_client.search(
            index_name=self.index_name,
            query=es_query["query"],
            size=1,
        )

        if results["hits"]["hits"]:
            project_data = results["hits"]["hits"][0]["_source"]
            return self.answer_generator.summarize_project(project_data)
        else:
            return f"Project '{project_name}' not found in the database."

    def compare_projects(
        self,
        query1: str,
        query2: str,
        label1: str = "First Set",
        label2: str = "Second Set",
    ) -> str:
        """
        Compare two sets of search results.

        Args:
            query1: First natural language query.
            query2: Second natural language query.
            label1: Label for first result set.
            label2: Label for second result set.

        Returns:
            Comparative answer.
        """
        results1 = self.search_only(query1, max_results=5)
        results2 = self.search_only(query2, max_results=5)

        question = f"Compare {label1} and {label2}"
        
        return self.answer_generator.generate_comparative_answer(
            question=question,
            results_list=[results1, results2],
            labels=[label1, label2],
        )

    def _error_response(self, message: str, return_metadata: bool) -> str | Dict[str, Any]:
        """Helper to format error responses."""
        if return_metadata:
            return {
                "answer": message,
                "sources": [],
                "total_results": 0,
                "results_shown": 0,
                "error": True,
            }
        return message

    def close(self):
        """Close connections."""
        self.es_client.close()
        logger.info("RAG Pipeline closed")