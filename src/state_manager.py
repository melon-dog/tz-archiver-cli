"""
State management for persistent storage of processed CIDs and errors.
Handles loading and saving of application state to disk.
"""

import json
from pathlib import Path
from typing import Set
from dataclasses import dataclass

from config import Config
from utils.logger import Logger


logger = Logger("StateManager")


@dataclass
class AppState:
    """Application state container."""

    processed_cids: Set[str]
    error_cids: Set[str]

    def __post_init__(self):
        """Ensure sets are properly initialized."""
        if not isinstance(self.processed_cids, set):
            self.processed_cids = (
                set(self.processed_cids) if self.processed_cids else set()
            )
        if not isinstance(self.error_cids, set):
            self.error_cids = set(self.error_cids) if self.error_cids else set()


class StateManager:
    """Manages persistent state storage and retrieval."""

    def __init__(self):
        self.processed_file = Config.PROCESSED_CIDS_FILE
        self.errors_file = Config.ERRORS_CIDS_FILE

    def _load_cids_from_file(self, file_path: Path) -> Set[str]:
        """Load CIDs from a JSON file."""
        if not file_path.exists():
            return set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            logger.error(f"Failed to load {file_path.name}: {e}")
            return set()

    def _save_cids_to_file(self, cids: Set[str], file_path: Path) -> bool:
        """Save CIDs to a JSON file."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(sorted(list(cids)), f, indent=2, ensure_ascii=False)
            return True
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save {file_path.name}: {e}")
            return False

    def load_state(self) -> AppState:
        """Load application state from disk."""
        processed_cids = self._load_cids_from_file(self.processed_file)
        error_cids = self._load_cids_from_file(self.errors_file)

        logger.info(f"Loaded {len(processed_cids)} processed CIDs")
        logger.info(f"Loaded {len(error_cids)} error CIDs")

        return AppState(processed_cids=processed_cids, error_cids=error_cids)

    def save_processed_cid(self, cid: str, state: AppState) -> bool:
        """Save a single processed CID immediately."""
        state.processed_cids.add(cid)
        return self._save_cids_to_file(state.processed_cids, self.processed_file)

    def save_error_cid(self, cid: str, state: AppState) -> bool:
        """Save a single error CID immediately."""
        state.error_cids.add(cid)
        return self._save_cids_to_file(state.error_cids, self.errors_file)

    def save_state(self, state: AppState) -> bool:
        """Save complete application state to disk."""
        processed_ok = self._save_cids_to_file(
            state.processed_cids, self.processed_file
        )
        errors_ok = self._save_cids_to_file(state.error_cids, self.errors_file)
        return processed_ok and errors_ok

    def is_processed(self, cid: str, state: AppState) -> bool:
        """Check if a CID has been processed."""
        return cid in state.processed_cids

    def is_error(self, cid: str, state: AppState) -> bool:
        """Check if a CID has errored."""
        return cid in state.error_cids
