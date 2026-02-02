"""Central configuration loaded from environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "github_projects")
ES_USERNAME = os.getenv("ES_USERNAME") or None
ES_PASSWORD = os.getenv("ES_PASSWORD") or None
ES_API_KEY = os.getenv("ES_API_KEY") or None

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")


def require_groq_api_key() -> str:
    """Return GROQ_API_KEY or raise."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is required")
    return GROQ_API_KEY


def require_github_token() -> str:
    """Return GITHUB_TOKEN or raise."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    return GITHUB_TOKEN
