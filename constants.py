"""Shared constants for data ingestion."""

from pathlib import Path

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = Path("data")

DEFAULT_PROJECTS_DIR = DATA_DIR / "raw" / "projects"
DEFAULT_COMMITS_DIR = DATA_DIR / "raw" / "commits"
DEFAULT_PROCESSED_DIR = DATA_DIR / "processed"
PAGE_SIZE = 100
