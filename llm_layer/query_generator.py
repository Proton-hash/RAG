"""
Query generator for converting natural language questions to Elasticsearch queries.
Uses LangChain with Groq LLM.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class QueryGenerator:
    """
    Generates Elasticsearch queries from natural language questions.
    """

    def __init__(
        self,
        groq_api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        temperature: float = 0.0,
        prompt_template_path: Optional[Path | str] = None,
    ):
        """
        Initialize the query generator.

        Args:
            groq_api_key: Groq API key for authentication.
            model_name: Name of the Groq model to use.
                Options: "llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
                        "mixtral-8x7b-32768", "gemma2-9b-it"
            temperature: Temperature for generation (0.0 = deterministic).
            prompt_template_path: Path to custom prompt template file.
        """
        self.llm = ChatGroq(
            api_key=groq_api_key,
            model_name=model_name,
            temperature=temperature,
        )

        # Load prompt template
        if prompt_template_path:
            template_path = Path(prompt_template_path)
        else:
            # Default to prompts/query_generation.txt
            template_path = Path(__file__).parent.parent / "prompts" / "query_generation.txt"

        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            template_text = f.read()

        self.prompt = PromptTemplate(
            template=template_text,
            input_variables=["schema", "question"],
        )

        # Create chain
        self.chain = self.prompt | self.llm | StrOutputParser()

        logger.info(f"QueryGenerator initialized with model: {model_name}")

    def get_index_schema(self, es_client, index_name: str) -> str:
        """
        Retrieve index mappings from Elasticsearch and format as schema.

        Args:
            es_client: Elasticsearch client instance.
            index_name: Name of the index.

        Returns:
            Formatted schema string.
        """
        try:
            mappings = es_client.client.indices.get_mapping(index=index_name)
            properties = mappings[index_name]["mappings"]["properties"]
            
            # Format schema in a readable way
            schema_lines = ["Field Name | Type | Description"]
            schema_lines.append("-" * 60)
            
            def format_properties(props, prefix=""):
                lines = []
                for field_name, field_info in props.items():
                    field_type = field_info.get("type", "object")
                    full_name = f"{prefix}{field_name}" if prefix else field_name
                    
                    if field_type == "nested":
                        lines.append(f"{full_name} | nested | Nested array of objects")
                        if "properties" in field_info:
                            lines.extend(format_properties(field_info["properties"], f"{full_name}."))
                    elif "properties" in field_info:
                        lines.append(f"{full_name} | object | Object with nested fields")
                        lines.extend(format_properties(field_info["properties"], f"{full_name}."))
                    else:
                        lines.append(f"{full_name} | {field_type} | ")
                
                return lines
            
            schema_lines.extend(format_properties(properties))
            schema_text = "\n".join(schema_lines)
            
            logger.debug(f"Retrieved schema for index '{index_name}'")
            return schema_text
            
        except Exception as e:
            logger.error(f"Error retrieving index schema: {e}")
            # Return a default schema as fallback
            return self._get_default_schema()

    def _get_default_schema(self) -> str:
        """Return default schema for GitHub projects index."""
        return """Field Name | Type | Description
------------------------------------------------------------
id | keyword | Project ID
name | text | Project name
full_name | text | Full project name (owner/repo)
description | text | Project description
language | keyword | Programming language
stargazers_count | integer | Number of stars
forks_count | integer | Number of forks
topics | keyword | Project topics/tags
created_at | date | Creation date
updated_at | date | Last update date
owner.login | keyword | Owner username
owner.type | keyword | Owner type (User/Organization)
commits | nested | Array of commit objects
commits.sha | keyword | Commit SHA
commits.commit.message | text | Commit message
commits.commit.author.name | text | Commit author name
commits.commit.author.date | date | Commit date"""

    def generate_query(
        self,
        question: str,
        es_client=None,
        index_name: str = "github_projects",
        schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate Elasticsearch query from natural language question.

        Args:
            question: Natural language question.
            es_client: Elasticsearch client (to fetch schema).
            index_name: Name of the index (for schema retrieval).
            schema: Optional pre-fetched schema string.

        Returns:
            Elasticsearch query as dictionary.

        Raises:
            ValueError: If generated query is invalid JSON.
        """
        # Get schema
        if schema is None:
            if es_client:
                schema = self.get_index_schema(es_client, index_name)
            else:
                schema = self._get_default_schema()
                logger.warning("No ES client provided, using default schema")

        # Generate query
        logger.info(f"Generating query for question: {question}")
        response = self.chain.invoke({
            "schema": schema,
            "question": question,
        })

        # Clean and parse response
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith("```"):
            # Remove ```json or ``` at start
            response = response.split("\n", 1)[1] if "\n" in response else response[3:]
        if response.endswith("```"):
            response = response.rsplit("\n", 1)[0] if "\n" in response else response[:-3]
        
        response = response.strip()

        try:
            query = json.loads(response)
            logger.info("Successfully generated Elasticsearch query")
            logger.debug(f"Generated query: {json.dumps(query, indent=2)}")
            return query
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse generated query as JSON: {e}")
            logger.error(f"Raw response: {response}")
            raise ValueError(f"Generated query is not valid JSON: {e}")

    def generate_and_validate_query(
        self,
        question: str,
        es_client=None,
        index_name: str = "github_projects",
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Generate query with automatic retry on failure.

        Args:
            question: Natural language question.
            es_client: Elasticsearch client.
            index_name: Name of the index.
            max_retries: Maximum number of retry attempts.

        Returns:
            Valid Elasticsearch query.

        Raises:
            ValueError: If query generation fails after retries.
        """
        for attempt in range(max_retries + 1):
            try:
                query = self.generate_query(
                    question=question,
                    es_client=es_client,
                    index_name=index_name,
                )
                return query
            except ValueError as e:
                if attempt < max_retries:
                    logger.warning(f"Query generation attempt {attempt + 1} failed, retrying...")
                else:
                    logger.error(f"Query generation failed after {max_retries + 1} attempts")
                    raise

    def test_query_generation(self, questions: list[str], es_client=None):
        """
        Test query generation with multiple questions.

        Args:
            questions: List of test questions.
            es_client: Elasticsearch client.

        Returns:
            List of tuples (question, query, success).
        """
        results = []
        for question in questions:
            try:
                query = self.generate_query(question, es_client)
                results.append((question, query, True))
                print(f"✓ {question}")
                print(f"  Query: {json.dumps(query, indent=2)}\n")
            except Exception as e:
                results.append((question, str(e), False))
                print(f"✗ {question}")
                print(f"  Error: {e}\n")
        
        success_rate = sum(1 for _, _, success in results if success) / len(results) * 100
        print(f"Success rate: {success_rate:.1f}% ({sum(1 for _, _, s in results if s)}/{len(results)})")
        
        return results