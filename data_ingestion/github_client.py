"""
GitHub API client with authentication, retry logic, and logging.
"""

import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class GitHubAPIClient:
    """
    A GitHub API client that:
    - Authenticates using a personal access token
    - Handles GET requests with automatic retry logic
    - Implements exponential backoff for rate limits
    - Returns JSON responses
    - Logs all requests and errors
    """

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        max_retries: int = 5,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the GitHub API client.

        Args:
            token: Personal access token for authentication.
            base_url: GitHub API base URL (default: https://api.github.com).
            max_retries: Maximum number of retry attempts for failed requests.
            initial_backoff: Initial backoff delay in seconds.
            max_backoff: Maximum backoff delay in seconds.
            timeout: Request timeout in seconds.
        """
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _get_full_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return f"{self.base_url}{path}"

    def _should_retry(self, response: Optional[requests.Response], error: Optional[Exception]) -> bool:
        """Determine if the request should be retried."""
        if error is not None:
            return True
        if response is None:
            return False
        # Retry on rate limit (403 with X-RateLimit-Remaining: 0, or 429) and server errors (5xx)
        if response.status_code in (429, 500, 502, 503, 504):
            return True
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            return True
        return False

    def _get_retry_after(self, response: requests.Response) -> Optional[float]:
        """Extract Retry-After header value if present."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return None

    def _compute_backoff(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Compute backoff delay in seconds."""
        if retry_after is not None:
            return min(retry_after, self.max_backoff)
        return min(self.initial_backoff * (2**attempt), self.max_backoff)

    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any]:
        """
        Perform a GET request to the GitHub API with retry logic.

        Args:
            endpoint: API endpoint path (e.g., "/repos/owner/repo" or "user").
            params: Optional query parameters.
            **kwargs: Additional arguments passed to requests.get.

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            requests.RequestException: If all retries are exhausted.
            ValueError: If the response is not valid JSON.
        """
        url = self._get_full_url(endpoint)
        last_response: Optional[requests.Response] = None
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info("GET request to %s (attempt %d/%d)", url, attempt + 1, self.max_retries + 1)
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    **kwargs,
                )
                last_response = response

                if response.ok:
                    logger.info("GET %s succeeded with status %d", url, response.status_code)
                    return response.json()

                logger.warning(
                    "GET %s returned status %d: %s",
                    url,
                    response.status_code,
                    response.text[:200] if response.text else "(no body)",
                )

                if not self._should_retry(response, None):
                    response.raise_for_status()

                backoff = self._compute_backoff(attempt, self._get_retry_after(response))
                if attempt < self.max_retries:
                    logger.info(
                        "Retrying in %.1f seconds (status %d)",
                        backoff,
                        response.status_code,
                    )
                    time.sleep(backoff)

            except requests.RequestException as e:
                last_error = e
                logger.error("GET request failed: %s", e, exc_info=True)
                if not self._should_retry(None, e) or attempt >= self.max_retries:
                    raise
                backoff = self._compute_backoff(attempt)
                logger.info("Retrying in %.1f seconds after error", backoff)
                time.sleep(backoff)

        # Exhausted retries
        if last_response is not None:
            last_response.raise_for_status()
        if last_error is not None:
            raise last_error
        raise requests.RequestException("Request failed after all retries")
