"""
Answer generator for creating natural language responses from Elasticsearch results.
Uses LangChain with Groq LLM.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """
    Generates natural language answers from Elasticsearch search results.
    """

    def __init__(
        self,
        groq_api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        prompt_template_path: Optional[Path | str] = None,
    ):
        """
        Initialize the answer generator.

        Args:
            groq_api_key: Groq API key for authentication.
            model_name: Name of the Groq model to use.
                Options: "llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
                        "mixtral-8x7b-32768", "gemma2-9b-it"
            temperature: Temperature for generation (0.0 = deterministic, 1.0 = creative).
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
            # Default to prompts/answer_generation.txt
            template_path = Path(__file__).parent.parent / "prompts" / "answer_generation.txt"

        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            template_text = f.read()

        self.prompt = PromptTemplate(
            template=template_text,
            input_variables=["question", "search_results"],
        )

        # Create chain
        self.chain = self.prompt | self.llm | StrOutputParser()

        logger.info(f"AnswerGenerator initialized with model: {model_name}")

    def format_search_results(
        self,
        results: Dict[str, Any],
        include_commits: bool = True,
        max_commits_per_project: int = 3,
    ) -> str:
        """
        Format Elasticsearch search results into readable text.

        Args:
            results: Raw Elasticsearch response.
            include_commits: Whether to include commit information.
            max_commits_per_project: Maximum commits to show per project.

        Returns:
            Formatted search results as string.
        """
        if not results or "hits" not in results or not results["hits"]["hits"]:
            return "No results found."

        formatted_lines = []
        hits = results["hits"]["hits"]
        total = results["hits"]["total"]["value"] if isinstance(results["hits"]["total"], dict) else results["hits"]["total"]
        
        formatted_lines.append(f"Found {total} total results. Showing top {len(hits)}:\n")

        for i, hit in enumerate(hits, 1):
            source = hit["_source"]
            
            # Project header
            formatted_lines.append(f"{i}. **{source.get('name', 'Unknown')}**")
            
            if "full_name" in source:
                formatted_lines.append(f"   Full Name: {source['full_name']}")
            
            if "description" in source and source["description"]:
                formatted_lines.append(f"   Description: {source['description']}")
            
            # Stats
            stats = []
            if "language" in source and source["language"]:
                stats.append(f"Language: {source['language']}")
            if "stargazers_count" in source:
                stats.append(f"⭐ {source['stargazers_count']} stars")
            if "forks_count" in source:
                stats.append(f"🍴 {source['forks_count']} forks")
            
            if stats:
                formatted_lines.append(f"   {' | '.join(stats)}")
            
            # Topics
            if "topics" in source and source["topics"]:
                topics = source["topics"][:5]  # Limit to 5 topics
                formatted_lines.append(f"   Topics: {', '.join(topics)}")
            
            # URL
            if "html_url" in source:
                formatted_lines.append(f"   URL: {source['html_url']}")
            
            # Commits (if included and present)
            if include_commits and "commits" in source and source["commits"]:
                commits = source["commits"][:max_commits_per_project]
                if commits:
                    formatted_lines.append(f"   Recent Commits ({len(source['commits'])} total):")
                    for commit in commits:
                        commit_info = commit.get("commit", {})
                        message = commit_info.get("message", "No message")
                        # Truncate long messages
                        if len(message) > 80:
                            message = message[:77] + "..."
                        author = commit_info.get("author", {}).get("name", "Unknown")
                        date = commit_info.get("author", {}).get("date", "")
                        if date:
                            date = date.split("T")[0]  # Just the date part
                        formatted_lines.append(f"     - {message}")
                        formatted_lines.append(f"       by {author}" + (f" on {date}" if date else ""))
            
            formatted_lines.append("")  # Empty line between projects

        return "\n".join(formatted_lines)

    def generate_answer(
        self,
        question: str,
        search_results: Dict[str, Any] | str,
        include_commits: bool = True,
    ) -> str:
        """
        Generate natural language answer from search results.

        Args:
            question: Original user question.
            search_results: Elasticsearch response (dict) or pre-formatted string.
            include_commits: Whether to include commit info in formatting.

        Returns:
            Natural language answer.
        """
        # Format results if needed
        if isinstance(search_results, dict):
            formatted_results = self.format_search_results(
                search_results,
                include_commits=include_commits,
            )
        else:
            formatted_results = search_results

        logger.info(f"Generating answer for question: {question}")
        
        # Generate answer
        answer = self.chain.invoke({
            "question": question,
            "search_results": formatted_results,
        })

        logger.info("Successfully generated answer")
        return answer.strip()

    def generate_answer_with_sources(
        self,
        question: str,
        search_results: Dict[str, Any],
        include_commits: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate answer with metadata and source information.

        Args:
            question: Original user question.
            search_results: Elasticsearch response.
            include_commits: Whether to include commit info.

        Returns:
            Dictionary with answer, sources, and metadata.
        """
        answer = self.generate_answer(question, search_results, include_commits)
        
        # Extract source information
        sources = []
        if "hits" in search_results and "hits" in search_results["hits"]:
            for hit in search_results["hits"]["hits"]:
                source = hit["_source"]
                sources.append({
                    "name": source.get("name"),
                    "full_name": source.get("full_name"),
                    "url": source.get("html_url"),
                    "description": source.get("description"),
                    "stars": source.get("stargazers_count"),
                    "language": source.get("language"),
                })
        
        total_results = search_results["hits"]["total"]
        if isinstance(total_results, dict):
            total_results = total_results["value"]
        
        return {
            "answer": answer,
            "sources": sources,
            "total_results": total_results,
            "results_shown": len(sources),
            "question": question,
        }

    def generate_comparative_answer(
        self,
        question: str,
        results_list: List[Dict[str, Any]],
        labels: List[str],
    ) -> str:
        """
        Generate answer comparing multiple search results.

        Args:
            question: Original question.
            results_list: List of Elasticsearch responses.
            labels: Labels for each result set.

        Returns:
            Comparative answer.
        """
        formatted_sections = []
        
        for label, results in zip(labels, results_list):
            formatted = self.format_search_results(results, include_commits=False)
            formatted_sections.append(f"## {label}\n{formatted}")
        
        combined_results = "\n\n".join(formatted_sections)
        
        return self.generate_answer(question, combined_results, include_commits=False)

    def summarize_project(self, project_data: Dict[str, Any]) -> str:
        """
        Generate a natural language summary of a single project.

        Args:
            project_data: Project data from Elasticsearch.

        Returns:
            Project summary.
        """
        # Create a mock search result with just this project
        mock_result = {
            "hits": {
                "total": {"value": 1},
                "hits": [{"_source": project_data}]
            }
        }
        
        question = f"Summarize the {project_data.get('name', 'project')} repository"
        return self.generate_answer(question, mock_result, include_commits=True)

    def test_answer_generation(
        self,
        test_cases: List[tuple[str, Dict[str, Any]]],
    ):
        """
        Test answer generation with multiple cases.

        Args:
            test_cases: List of (question, search_results) tuples.

        Returns:
            List of (question, answer, success) tuples.
        """
        results = []
        for question, search_results in test_cases:
            try:
                answer = self.generate_answer(question, search_results)
                results.append((question, answer, True))
                print(f"✓ Question: {question}")
                print(f"  Answer: {answer}\n")
            except Exception as e:
                results.append((question, str(e), False))
                print(f"✗ Question: {question}")
                print(f"  Error: {e}\n")
        
        success_rate = sum(1 for _, _, success in results if success) / len(results) * 100
        print(f"Success rate: {success_rate:.1f}% ({sum(1 for _, _, s in results if s)}/{len(results)})")
        
        return results