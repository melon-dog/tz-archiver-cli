"""
Configuration module for TZ Archiver CLI.
Centralizes all configuration constants and settings.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Application configuration constants."""

    # Application info
    APP_NAME = "tz-archiver-cli"
    VERSION = "1.0.0"

    # Wayback Machine limits
    WAYBACK_RATE_LIMIT = 12  # captures per minute
    MAX_CONCURRENT_PROCESSES = 4

    # Default values
    DEFAULT_TOKEN_LIMIT = 10_000
    DEFAULT_SPIDER_BATCH_SIZE = 10_000
    DEFAULT_SPIDER_DELAY = 0.5

    # API settings
    TZKT_API_DELAY = 0.1  # seconds between requests
    WAYBACK_TIMEOUT = 15  # seconds

    # File settings
    SCRIPT_DIR = Path(__file__).parent
    DATA_DIR = SCRIPT_DIR / "data"
    PROCESSED_CIDS_FILE = DATA_DIR / "processed_cids.json"
    ERRORS_CIDS_FILE = DATA_DIR / "errors_cids.json"

    # IPFS settings
    IPFS_GATEWAY = "https://ipfs.fileship.xyz"

    # Wayback Machine settings
    WAYBACK_JS_TIMEOUT = 7
    WAYBACK_DELAY_AVAILABILITY = False
    WAYBACK_IF_NOT_ARCHIVED_WITHIN = 31_536_000  # 1 year in seconds

    @classmethod
    def ensure_data_dir(cls) -> None:
        """Ensure the data directory exists."""
        cls.DATA_DIR.mkdir(exist_ok=True)

    @classmethod
    def get_env_var(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable with optional default."""
        return os.getenv(key, default)

    @classmethod
    def get_archive_credentials(cls) -> tuple[Optional[str], Optional[str]]:
        """Get Internet Archive credentials from environment."""
        access_key = cls.get_env_var("ARCHIVE_ACCESS")
        secret_key = cls.get_env_var("ARCHIVE_SECRET")
        return access_key, secret_key


# Initialize data directory on import
Config.ensure_data_dir()
